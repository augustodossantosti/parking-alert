import os
import numpy as np
import cv2
import mrcnn.config
import mrcnn.utils
from mrcnn.model import MaskRCNN
from pathlib import Path

# Configuration that will be used by the Mask-RCNN library


class MaskRCNNConfig(mrcnn.config.Config):
    NAME = "coco_pretrained_model_config"
    IMAGES_PER_GPU = 1
    GPU_COUNT = 1
    NUM_CLASSES = 1 + 80  # COCO dataset has 80 classes + one background class
    DETECTION_MIN_CONFIDENCE = 0.6


class Analisador:

    def __init__(self):
        """ Inicializa o  objeto responsavel pela verificação das vagas """

        # Root directory of the project
        ROOT_DIR = Path(".")

        # Directory to save logs and trained model
        MODEL_DIR = os.path.join(ROOT_DIR, "logs")

        # Local path to trained weights file
        COCO_MODEL_PATH = os.path.join(ROOT_DIR, "mask_rcnn_coco.h5")

        # Download COCO trained weights from Releases if needed
        if not os.path.exists(COCO_MODEL_PATH):
            mrcnn.utils.download_trained_weights(COCO_MODEL_PATH)

        # Directory of images to run detection on
        IMAGE_DIR = os.path.join(ROOT_DIR, "images")

        # Video file or camera to process - set this to 0 to use your webcam instead of a video file
        VIDEO_SOURCE = "test_images/parking-sd.mp4"

        # Create a Mask-RCNN model in inference mode
        self.model = MaskRCNN(
            mode="inference", model_dir=MODEL_DIR, config=MaskRCNNConfig())

        # Load pre-trained model
        self.model.load_weights(COCO_MODEL_PATH, by_name=True)

        # Load the video file we want to run detection on
        self.video_capture = cv2.VideoCapture(VIDEO_SOURCE)

        # How many frames of video we've seen in a row with a parking space open
        self.free_space_frames = 0

    # Filter a list of Mask R-CNN detection results to get only the detected cars / trucks
    def get_car_boxes(self, boxes, class_ids):
        car_boxes = []

        for i, box in enumerate(boxes):
            # If the detected object isn't a car / truck, skip it
            if class_ids[i] in [3, 8, 6]:
                car_boxes.append(box)

        return np.array(car_boxes)

    def analisar(self) -> int:

        # Location of parking spaces
        parked_car_boxes = None

        # Loop over each frame of video
        while self.video_capture.isOpened():
            success, frame = self.video_capture.read()
            if not success:
                break

            # Convert the image from BGR color (which OpenCV uses) to RGB color
            rgb_image = frame[:, :, ::-1]

            # Run the image through the Mask R-CNN model to get results.
            results = self.model.detect([rgb_image], verbose=0)

            # Mask R-CNN assumes we are running detection on multiple images.
            # We only passed in one image to detect, so only grab the first result.
            r = results[0]

            # The r variable will now have the results of detection:
            # - r['rois'] are the bounding box of each detected object
            # - r['class_ids'] are the class id (type) of each detected object
            # - r['scores'] are the confidence scores for each detection
            # - r['masks'] are the object masks for each detected object (which gives you the object outline)

            if parked_car_boxes is None:
                # This is the first frame of video - assume all the cars detected are in parking spaces.
                # Save the location of each car as a parking space box and go to the next frame of video.
                parked_car_boxes = self.get_car_boxes(
                    r['rois'], r['class_ids'])
            else:
                # We already know where the parking spaces are. Check if any are currently unoccupied.

                # Get where cars are currently located in the frame
                car_boxes = self.get_car_boxes(r['rois'], r['class_ids'])

                # See how much those cars overlap with the known parking spaces
                overlaps = mrcnn.utils.compute_overlaps(
                    parked_car_boxes, car_boxes)

                # Assume no spaces are free until we find one that is free
                free_space = False

                # Loop through each known parking space box
                for parking_area, overlap_areas in zip(parked_car_boxes, overlaps):

                    # For this parking space, find the max amount it was covered by any
                    # car that was detected in our image (doesn't really matter which car)
                    max_IoU_overlap = np.max(overlap_areas)

                    # Get the top-left and bottom-right coordinates of the parking area
                    y1, x1, y2, x2 = parking_area

                    # Check if the parking space is occupied by seeing if any car overlaps
                    # it by more than 0.15 using IoU
                    if max_IoU_overlap < 0.15:
                        # Parking space not occupied! Draw a green box around it
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                        # Flag that we have seen at least one open space
                        free_space = True
                    else:
                        # Parking space is still occupied - draw a red box around it
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 1)

                    # Write the IoU measurement inside the box
                    font = cv2.FONT_HERSHEY_DUPLEX
                    cv2.putText(frame, f"{max_IoU_overlap:0.2}", (x1 + 6, y2 - 6), font, 0.3, (255, 255, 255))

                # If at least one space was free, start counting frames
                # This is so we don't alert based on one frame of a spot being open.
                # This helps prevent the script triggered on one bad detection.
                if free_space:
                    free_space_frames += 1
                else:
                    # If no spots are free, reset the count
                    free_space_frames = 0

                # If a space has been free for several frames, we are pretty sure it is really free!
                if free_space_frames > 10:
                    # Write SPACE AVAILABLE!! at the top of the screen
                    font = cv2.FONT_HERSHEY_DUPLEX
                    cv2.putText(frame, f"SPACE AVAILABLE!", (10, 150),
                                font, 3.0, (0, 255, 0), 2, cv2.FILLED)

                    # If we haven't sent an SMS yet, sent it!
                    if not sms_sent:
                        print("Vaga encontrada!!!")
                        self.close_app()
                        return 1

                # Show the frame of video on the screen
                cv2.imshow('Video', frame)

            # Hit 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    def close_app(self):

        # Clean up everything when finished
        self.video_capture.release()
        cv2.destroyAllWindows()

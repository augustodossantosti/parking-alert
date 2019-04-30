from flask import Flask
from flask import jsonify

app = Flask(__name__)


@app.route('/')
def listar_vagas():
    return jsonify({'vagas': 5})


if __name__ == '__main__':
    app.run()

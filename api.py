from flask import Flask
from flask import jsonify
from open_parking_alert import Analisador

app = Flask(__name__)


@app.route('/')
def listar_vagas():
    analisador = Analisador()
    vagas = analisador.analisar()
    return jsonify({'vagas': vagas})


if __name__ == '__main__':
    app.run()

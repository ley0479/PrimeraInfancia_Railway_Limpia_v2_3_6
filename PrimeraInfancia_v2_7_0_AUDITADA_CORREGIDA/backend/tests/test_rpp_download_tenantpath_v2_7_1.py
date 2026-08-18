from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    source = (ROOT / "backend" / "app.py").read_text(encoding="utf-8")
    route = source.split("def descargar_rpp_por_categoria():", 1)[1].split("@app.route('/api/descargar-archivo", 1)[0]
    assert "'output_folder': os.fspath(OUTPUT_FOLDER)" in route
    assert "return jsonify(payload), 404" in route
    assert "No existe un RPP generado para esa unidad y grupo exactos." in route
    print("OK: RPP no generado responde 404 serializable y no 409")


if __name__ == "__main__":
    main()

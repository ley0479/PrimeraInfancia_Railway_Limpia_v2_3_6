from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'onclick="actualizarTalentoIntegral()"' in html
    assert 'id="th-integral-estado"' in html
    assert "async function actualizarTalentoIntegral()" in js
    function = js.split("async function actualizarTalentoIntegral()", 1)[1].split("async function fetchTalentoIntegral()", 1)[0]
    assert "/api/talento-core/sincronizar" in function
    assert "method:'POST'" in function
    assert "await fetchTalentoIntegral()" in function
    assert function.index("/api/talento-core/sincronizar") < function.index("await fetchTalentoIntegral()")
    assert "La fuente maestra está vacía" in function
    print("OK: Actualizar tablero sincroniza primero y reporta fuente vacía")


if __name__ == "__main__":
    main()

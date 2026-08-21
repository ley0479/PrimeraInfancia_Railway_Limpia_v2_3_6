from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.data_import import UniversalMappingService
from services.data_import.normalizers import normalize_header, normalize_unit_code


HEADERS = [
    "Tipo de documento del beneficiario", "Documento del beneficiario",
    "Primer nombre del beneficiario", "Primer apellido del beneficiario", "Estado del beneficiario",
    "Nombre de la Regional de la Unidad de servicio", "Código del Municipio de la Unidad de servicio",
    "Nombre Municipio de la Unidad de servicio", "Nombre del Centro Zonal",
    "Código de la unidad de servicio", "Nombre de la unidad de servicio",
] + [f"Campo adicional {i}" for i in range(30)]


def build_fixture(path: Path, header_row: int = 1, shuffled: bool = False) -> None:
    workbook = Workbook()
    info = workbook.active
    info.title = "Instrucciones"
    info.append(["Archivo de intercambio; no contiene registros"])
    sheet = workbook.create_sheet("ICBFCUEBeneficiariosPIActivosRe")
    for _ in range(header_row - 1): sheet.append(["INSTITUTO COLOMBIANO DE BIENESTAR FAMILIAR"])
    headers = list(HEADERS)
    if shuffled: headers = headers[9:11] + headers[:9] + headers[11:]
    sheet.append(headers)
    for index in range(417):
        unit = index % 39
        values = {
            "Tipo de documento del beneficiario": "RC", "Documento del beneficiario": f"10{index:08d}",
            "Primer nombre del beneficiario": f"NOMBRE{index}", "Primer apellido del beneficiario": f"APELLIDO{index}",
            "Estado del beneficiario": "ACTIVO", "Nombre de la Regional de la Unidad de servicio": "Chocó",
            "Código del Municipio de la Unidad de servicio": "27001", "Nombre Municipio de la Unidad de servicio": "QUIBDÓ",
            "Nombre del Centro Zonal": "CENTRO ZONAL 1", "Código de la unidad de servicio": (f"0{unit:011d}" if unit % 2 else f"1{unit:012d}"),
            "Nombre de la unidad de servicio": f"UDS {unit + 1:02d}",
        }
        sheet.append([values.get(header, f"V{index}") for header in headers])
    workbook.save(path)


class UniversalMapperRegressionTests(unittest.TestCase):
    def analyze(self, header_row=1, shuffled=False):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "base_desconocida.xlsx"
            build_fixture(path, header_row, shuffled)
            return UniversalMappingService().analyze(str(path))

    def test_regression_regional_is_not_unit(self):
        result = self.analyze()
        self.assertEqual(result["selected_table"], "ICBFCUEBeneficiariosPIActivosRe")
        self.assertEqual(result["preview"]["header_row"], 1)
        self.assertEqual(result["mapping"]["unidad.codigo"]["selected"]["original_header"], "Código de la unidad de servicio")
        self.assertEqual(result["mapping"]["unidad.nombre"]["selected"]["original_header"], "Nombre de la unidad de servicio")
        self.assertEqual(result["mapping"]["regional.nombre"]["selected"]["original_header"], "Nombre de la Regional de la Unidad de servicio")
        self.assertEqual(result["mapping"]["municipio.codigo"]["selected"]["original_header"], "Código del Municipio de la Unidad de servicio")
        self.assertEqual(result["mapping"]["municipio.nombre"]["selected"]["original_header"], "Nombre Municipio de la Unidad de servicio")
        self.assertEqual(result["mapping"]["centro_zonal.nombre"]["selected"]["original_header"], "Nombre del Centro Zonal")
        self.assertEqual(result["units"]["count"], 39)
        self.assertEqual(result["units"]["missing_code"], 0)
        self.assertEqual(result["units"]["missing_name"], 0)
        self.assertNotIn("Chocó", {item["name"] for item in result["units"]["items"]})

    def test_reordered_columns_and_header_at_row_20(self):
        result = self.analyze(header_row=20, shuffled=True)
        self.assertEqual(result["preview"]["header_row"], 20)
        self.assertEqual(result["units"]["count"], 39)

    def test_normalization_and_codes(self):
        self.assertEqual(normalize_header(" Nombre\u00a0 de\n U.D.S. "), "nombre de u d s")
        self.assertEqual(normalize_unit_code("001234567890"), "001234567890")
        self.assertEqual(normalize_unit_code("1234567890123.0"), "1234567890123")
        self.assertEqual(normalize_unit_code("1.234E+12"), "1234000000000")


if __name__ == "__main__":
    unittest.main()

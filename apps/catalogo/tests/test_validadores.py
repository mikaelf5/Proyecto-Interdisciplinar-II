from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.catalogo.dominio.validadores import validar_atributos, validar_definicion

DEF_EQUIPO = {
    "nombre": {"tipo": "texto", "requerido": True},
    "numero_serie": {"tipo": "texto", "requerido": True},
    "anio": {"tipo": "entero", "requerido": False},
}


class ValidadoresTests(SimpleTestCase):
    def test_atributos_validos(self):
        validar_atributos({"nombre": "Laptop", "numero_serie": "X1"}, DEF_EQUIPO)

    def test_falta_obligatorio(self):
        with self.assertRaises(ValidationError):
            validar_atributos({"nombre": "Laptop"}, DEF_EQUIPO)

    def test_tipo_incorrecto(self):
        with self.assertRaises(ValidationError):
            validar_atributos({"nombre": "Laptop", "numero_serie": "X1", "anio": "2020"}, DEF_EQUIPO)

    def test_atributo_no_definido(self):
        with self.assertRaises(ValidationError):
            validar_atributos({"nombre": "Laptop", "numero_serie": "X1", "color": "rojo"}, DEF_EQUIPO)

    def test_definicion_con_tipo_invalido(self):
        with self.assertRaises(ValidationError):
            validar_definicion({"x": {"tipo": "imagen"}})

from django import forms

from apps.common.choices import EstadoItem


class FiltroItemForm(forms.Form):
    """Formulario de búsqueda del catálogo (no está ligado a un modelo)."""
    texto = forms.CharField(
        required=False, label="Buscar",
        widget=forms.TextInput(attrs={"placeholder": "Código, título, autor, marca…", "class": "form-control"}),
    )
    categoria_id = forms.ChoiceField(required=False, label="Categoría",
                                     widget=forms.Select(attrs={"class": "form-select"}))
    estado = forms.ChoiceField(
        required=False, label="Estado",
        choices=[("", "Todos")] + list(EstadoItem.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, categorias=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria_id"].choices = [("", "Todas")] + [(str(c.id), c.nombre) for c in categorias]



CONTROL = {"class": "form-control"}


def _campo_texto(etiqueta, requerido, regla):
    return forms.CharField(label=etiqueta, required=requerido, max_length=200,
                           widget=forms.TextInput(attrs=CONTROL))


def _campo_entero(etiqueta, requerido, regla):
    return forms.IntegerField(label=etiqueta, required=requerido, widget=forms.NumberInput(attrs=CONTROL))


def _campo_numero(etiqueta, requerido, regla):
    return forms.FloatField(label=etiqueta, required=requerido, widget=forms.NumberInput(attrs=CONTROL))


def _campo_booleano(etiqueta, requerido, regla):
    return forms.BooleanField(label=etiqueta, required=False,
                              widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))


def _campo_fecha(etiqueta, requerido, regla):
    return forms.DateField(label=etiqueta, required=requerido,
                           widget=forms.DateInput(attrs={**CONTROL, "type": "date"}))


def _campo_opcion(etiqueta, requerido, regla):
    opciones = [("", "— Elige —")] + [(opcion, opcion) for opcion in regla.get("opciones", [])]
    return forms.ChoiceField(label=etiqueta, required=requerido, choices=opciones,
                             widget=forms.Select(attrs={"class": "form-select"}))


class ItemNuevoForm(forms.Form):
    """
    Registro de un ítem (RF-A2). Los campos de atributos se ARMAN SOLOS según la
    definición de la categoría elegida (RNF-9: sin tocar código al crear categorías).

        definicion_atributos = {"autor": {"tipo": "texto", "requerido": true}, ...}
        → aparece un campo "Autor" obligatorio de texto.
    """
    PREFIJO = "attr_"
    CAMPOS_POR_TIPO = {
        "texto": _campo_texto,
        "entero": _campo_entero,
        "numero": _campo_numero,
        "booleano": _campo_booleano,
        "fecha": _campo_fecha,
        "opcion": _campo_opcion,
    }

    codigo = forms.CharField(
        label="Código", max_length=50,
        widget=forms.TextInput(attrs={**CONTROL, "placeholder": "Ej.: LIB-005"}),
    )

    def __init__(self, *args, definicion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.definicion = definicion or {}
        for nombre, regla in self.definicion.items():
            self.fields[self.PREFIJO + nombre] = self._campo(nombre, regla)

    @classmethod
    def _campo(cls, nombre, regla):
        """Crea el campo según el tipo del atributo (texto, entero, fecha, opción…)."""
        tipo = regla.get("tipo", "texto")
        crear_campo = cls.CAMPOS_POR_TIPO.get(tipo, _campo_texto)
        return crear_campo(etiqueta=nombre.replace("_", " ").capitalize(),
                           requerido=bool(regla.get("requerido", False)), regla=regla)

    @classmethod
    def valores_actuales(cls, item):
        """Para la pantalla Editar: el formulario aparece lleno con lo que el ítem ya tiene."""
        return {"codigo": item.codigo, **{cls.PREFIJO + nombre: valor for nombre, valor in item.atributos.items()}}

    def campos_de_atributos(self):
        return [self[self.PREFIJO + n] for n in self.definicion]

    def atributos(self):
        """Arma el JSON de atributos con lo que se escribió, sin incluir los campos vacíos."""
        escritos = {nombre: self.cleaned_data.get(self.PREFIJO + nombre) for nombre in self.definicion}
        return {nombre: self._como_json(valor) for nombre, valor in escritos.items() if self._tiene_valor(valor)}

    @staticmethod
    def _tiene_valor(valor):
        return valor is not None and valor != ""

    @staticmethod
    def _como_json(valor):
        """Las fechas se guardan como texto AAAA-MM-DD; lo demás tal cual."""
        return valor.isoformat() if hasattr(valor, "isoformat") else valor

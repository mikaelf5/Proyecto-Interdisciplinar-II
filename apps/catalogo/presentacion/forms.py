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


def _nombre_campo(categoria_id, atributo):
    """Nombre del campo HTML de un atributo dinámico de una categoría."""
    return f"attr__{categoria_id}__{atributo}"


def _campo_para(nombre, regla):
    """Crea el campo de formulario que corresponde al tipo del atributo."""
    tipo = regla.get("tipo", "texto")
    requerido = bool(regla.get("requerido", False))
    etiqueta = nombre.replace("_", " ").capitalize() + (" *" if requerido else "")
    # required=False: la obligatoriedad se revisa solo para la categoría elegida.
    comun = {"required": False, "label": etiqueta}
    if tipo == "entero":
        return forms.IntegerField(widget=forms.NumberInput(attrs={"class": "form-control"}), **comun)
    if tipo == "numero":
        return forms.FloatField(widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}), **comun)
    if tipo == "booleano":
        return forms.BooleanField(widget=forms.CheckboxInput(attrs={"class": "form-check-input"}), **comun)
    if tipo == "fecha":
        return forms.DateField(widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}), **comun)
    if tipo == "opcion":
        opciones = [("", "— Elige —")] + [(o, o) for o in regla.get("opciones", [])]
        return forms.ChoiceField(choices=opciones, widget=forms.Select(attrs={"class": "form-select"}), **comun)
    return forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "form-control"}), **comun)


class ItemForm(forms.Form):
    """Formulario para registrar un ítem nuevo.

    Además de código y categoría, crea un campo por cada atributo definido en
    cada categoría (Categoria.definicion_atributos). En la página solo se
    muestran los de la categoría elegida, y al validar solo se toman esos.
    """
    codigo = forms.CharField(
        max_length=50, label="Código",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. LIB-005"}),
    )
    categoria_id = forms.ChoiceField(
        label="Categoría", widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, categorias=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.categorias = {str(c.id): c for c in categorias}
        self.fields["categoria_id"].choices = [("", "— Elige una categoría —")] + [
            (str(c.id), c.nombre + (" (especial)" if c.es_especial else ""))
            for c in categorias
        ]
        self._grupos = []
        for c in categorias:
            nombres = []
            for atributo, regla in (c.definicion_atributos or {}).items():
                nombre = _nombre_campo(c.id, atributo)
                self.fields[nombre] = _campo_para(atributo, regla)
                nombres.append(nombre)
            self._grupos.append((c, nombres))

    @property
    def grupos_atributos(self):
        return [(c, [self[n] for n in nombres]) for c, nombres in self._grupos]

    def clean_codigo(self):
        return self.cleaned_data["codigo"].strip().upper()

    def clean(self):
        datos = super().clean()
        categoria = self.categorias.get(datos.get("categoria_id") or "")
        if categoria is None:
            return datos
        
        atributos = {}
        for atributo, regla in (categoria.definicion_atributos or {}).items():
            nombre = _nombre_campo(categoria.id, atributo)
            valor = datos.get(nombre)
            vacio = valor in (None, "") or (regla.get("tipo") == "booleano" and valor is False and regla.get("requerido"))
            
            if regla.get("tipo") == "booleano" and not regla.get("requerido"):
                atributos[atributo] = bool(valor)
                continue

            if vacio:
                if regla.get("requerido"):
                    self.add_error(nombre, "Este atributo es obligatorio.")
                continue

            if regla.get("tipo") == "fecha":
                valor = valor.isoformat()
                
            if isinstance(valor, str):
                valor = valor.strip()
            atributos[atributo] = valor
        datos["atributos"] = atributos
        return datos
    
class MotivoForm(forms.Form):
    motivo = forms.CharField(max_length=255, label="Motivo")

import uuid

from django import forms

from .infraestructura import consultas
from .models import Sancion, TipoSancion


class _SelectConDatos(forms.Select):
    """Select que agrega data-solicitante a cada opción (para filtrar los préstamos en pantalla)."""

    def __init__(self, *args, datos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.datos = datos or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcion = super().create_option(name, value, label, selected, index, subindex, attrs)
        dueno = self.datos.get(str(value))
        if dueno:
            opcion["attrs"]["data-solicitante"] = dueno
        return opcion


def _uuid(valor):
    return uuid.UUID(str(valor))


class SancionForm(forms.ModelForm):
    """Quién aplica la sanción y si está activa se manejan solos (no se piden).

    El solicitante se elige por nombre, DNI o CUI entre las cuentas con rol Solicitante:
    a otros roles no se les puede sancionar. El préstamo se elige por su fecha e ítem.
    """

    solicitante_id = forms.TypedChoiceField(
        label="Solicitante", coerce=_uuid, empty_value=None,
        widget=forms.Select(attrs={"class": "form-select", "size": 6}),
        help_text="Escribe en el buscador para filtrar. Solo aparecen cuentas con rol Solicitante.",
    )
    prestamo_id = forms.TypedChoiceField(
        label="Préstamo relacionado", coerce=_uuid, empty_value=None, required=False,
        help_text="Opcional: préstamo que originó la sanción (se muestran los del solicitante elegido).",
    )

    class Meta:
        model = Sancion
        fields = [
            "solicitante_id",
            "prestamo_id",
            "tipo",
            "motivo",
            "duracion_dias",
            "fecha_inicio",
        ]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "motivo": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "duracion_dias": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "fecha_inicio": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"
            ),
        }
        help_texts = {
            "motivo": "Obligatorio: queda registrado también en la auditoría.",
            "duracion_dias": "Obligatorio para suspensión temporal; vacío = sin plazo.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cuentas = consultas.solicitantes()
        self._solicitantes = {str(c.pk) for c in cuentas}
        opciones = [(str(c.pk), consultas.etiqueta_persona(c)) for c in cuentas]

        # Al editar una sanción antigua cuya persona ya no es solicitante, se mantiene visible.
        actual = self.instance.solicitante_id if self.instance.pk else None
        if actual and str(actual) not in self._solicitantes:
            nombre = consultas.personas({actual}).get(actual, (str(actual)[:8], ""))[0]
            opciones.append((str(actual), f"{nombre} (ya no tiene rol Solicitante)"))
        self.fields["solicitante_id"].choices = [("", "— Elige un solicitante —")] + opciones

        incluir = {self.instance.prestamo_id, _uuid_o_none(self.initial.get("prestamo_id"))}
        prestamos = consultas.prestamos_recientes(incluir=incluir - {None})
        self._duenos = {str(pid): str(sid) for pid, sid, _ in prestamos}
        campo = self.fields["prestamo_id"]
        campo.choices = [("", "— Ninguno —")] + [(str(pid), etiqueta) for pid, _, etiqueta in prestamos]
        campo.widget = _SelectConDatos(attrs={"class": "form-select"}, datos=self._duenos)
        campo.widget.choices = campo.choices
        self.fields["tipo"].choices = [("", "— Elige el tipo —")] + list(TipoSancion.choices)

    def clean_motivo(self):
        motivo = self.cleaned_data["motivo"].strip()
        if len(motivo) < 5:
            raise forms.ValidationError("Describe el motivo (mínimo 5 caracteres).")
        return motivo

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo")
        duracion = datos.get("duracion_dias")
        if tipo == TipoSancion.SUSPENSION_TEMPORAL and not duracion:
            self.add_error(
                "duracion_dias",
                "La suspensión temporal necesita una duración en días.",
            )
        solicitante = datos.get("solicitante_id")
        es_la_misma = self.instance.pk and solicitante == self.instance.solicitante_id
        if solicitante and str(solicitante) not in self._solicitantes and not es_la_misma:
            self.add_error("solicitante_id", "Solo se puede sancionar a cuentas con rol Solicitante.")
        prestamo = datos.get("prestamo_id")
        if prestamo and solicitante and self._duenos.get(str(prestamo)) != str(solicitante):
            self.add_error("prestamo_id", "Ese préstamo no es del solicitante elegido.")
        return datos


def _uuid_o_none(valor):
    try:
        return _uuid(valor) if valor else None
    except ValueError:
        return None

"""
Capa de PRESENTACIÓN — ReservaController.

Cada vista: 1) lee la petición, 2) llama al servicio de aplicación, 3) muestra
el resultado. El acceso se controla por ROL (RolRequeridoMixin de Identidad).

Mapa rápido (pantalla → URL → vista → servicio):
    Reservar ............ /reservas/item/<id>/reservar/  ReservarView         crear / anotarse_en_espera
    Mis reservas ........ /reservas/mias/                MisReservasView      mis_reservas
    Cancelar ............ /reservas/<id>/cancelar/       CancelarView         cancelar
    Agenda del ítem ..... /reservas/item/<id>/agenda/    AgendaView           agenda
    Anular (encargado) .. /reservas/<id>/anular/         AnularView           anular
    Bandeja supervisor .. /reservas/supervisor/          BandejaSupervisorView en_espera_supervisor
    Aprobar / Rechazar .. /reservas/<id>/aprobar|rechazar/                    aprobar_supervisor / rechazar_supervisor
"""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from apps.common.choices import EstadoReserva, RolSistema
from apps.identidad.presentacion.permisos import RolRequeridoMixin

from ..aplicacion.dtos import NuevaReservaDTO
from ..aplicacion.servicios import ReservaServicioAplicacion
from ..dominio.excepciones import HorarioOcupado
from .forms import MotivoForm, ReservaForm

ROLES_GESTION = (RolSistema.ENCARGADO, RolSistema.ADMINISTRADOR)


def _servicio():
    return ReservaServicioAplicacion()


def _tiene_rol(usuario, *roles):
    return usuario.is_authenticated and (usuario.is_superuser or usuario.tiene_algun_rol(*roles))


def _errores(error):
    return " ".join(error.messages) if hasattr(error, "messages") else str(error)


def _nombres(cuenta_ids):
    """{cuenta_id: nombres}, con la API pública de Django (sin entrar al módulo Identidad)."""
    return {c.pk: c.nombres for c in get_user_model().objects.filter(pk__in=set(cuenta_ids))}


def _item_o_none(servicio, item_id):
    try:
        return servicio.catalogo.obtener_item(item_id)
    except ValidationError:
        return None


def _items_de(servicio, reservas):
    """{item_id: ItemDTO} de las reservas, para mostrar el código y nombre del ítem."""
    return {item_id: _item_o_none(servicio, item_id) for item_id in {r.item_id for r in reservas}}


def _fecha_pedida(request):
    return parse_date(request.GET.get("fecha", "")) or timezone.localdate()


def _volver(request, por_defecto):
    """Vuelve a la página indicada en `next` (solo si es de nuestro sitio)."""
    siguiente = request.POST.get("next", "")
    if siguiente and url_has_allowed_host_and_scheme(siguiente, allowed_hosts={request.get_host()}):
        return redirect(siguiente)
    return redirect(por_defecto)


class ReservarView(RolRequeridoMixin, View):
    """
    Pantalla: "Reservar" (botón "Reservar este ítem" del detalle del catálogo).
    GET  → muestra el formulario y la disponibilidad del día.
    POST → botón "Reservar" (servicio.crear) o "Avisarme si se libera" (servicio.anotarse_en_espera).
    Si el horario choca, se vuelve a mostrar el formulario con horarios libres y otros ítems.
    """
    roles_permitidos = [RolSistema.SOLICITANTE]
    template_name = "reservas/reservar.html"

    def get(self, request, item_id):
        servicio = _servicio()
        item = _item_o_none(servicio, item_id)
        if item is None:
            return self._item_no_existe(request)
        fecha = _fecha_pedida(request)
        form = ReservaForm(initial={"fecha": fecha})
        return render(request, self.template_name, self._contexto(servicio, item, form, fecha))

    def post(self, request, item_id):
        servicio = _servicio()
        item = _item_o_none(servicio, item_id)
        if item is None:
            return self._item_no_existe(request)

        form = ReservaForm(request.POST)
        conflicto = None
        if form.is_valid():
            try:
                self._ejecutar(request, servicio, self._dto(request, item, form))
                return redirect("reservas:mias")
            except HorarioOcupado as error:
                conflicto = error
            except ValidationError as error:
                for mensaje in error.messages:
                    form.add_error(None, mensaje)

        fecha = form.cleaned_data.get("fecha") or timezone.localdate()
        contexto = self._contexto(servicio, item, form, fecha)
        contexto["conflicto"] = conflicto
        return render(request, self.template_name, contexto)

    @staticmethod
    def _dto(request, item, form):
        datos = form.cleaned_data
        return NuevaReservaDTO(
            solicitante_id=request.user.id, item_id=item.id, fecha=datos["fecha"],
            hora_inicio=datos["hora_inicio"], hora_fin=datos["hora_fin"], finalidad=datos["finalidad"],
        )

    def _ejecutar(self, request, servicio, dto):
        if request.POST.get("accion") == "espera":
            self._anotarse_en_espera(request, servicio, dto)
        else:
            self._reservar(request, servicio, dto)

    @staticmethod
    def _reservar(request, servicio, dto):
        reserva = servicio.crear(dto)
        if reserva.estado == EstadoReserva.EN_ESPERA_SUPERVISOR:
            messages.info(request, f"Reserva registrada para el {reserva.franja}. Como es un ítem "
                                   f"especial, falta la aprobación del supervisor.")
        else:
            messages.success(request, f"¡Reserva confirmada para el {reserva.franja}!")

    @staticmethod
    def _anotarse_en_espera(request, servicio, dto):
        reserva = servicio.anotarse_en_espera(dto)
        messages.success(request, f"Te anotamos en la lista de espera (posición n.º "
                                  f"{reserva.posicion_en_cola}). Te avisaremos si se libera.")

    @staticmethod
    def _item_no_existe(request):
        messages.error(request, "El ítem no existe.")
        return redirect("catalogo:buscar")

    @staticmethod
    def _contexto(servicio, item, form, fecha):
        return {
            "item": item, "form": form, "fecha": fecha,
            "agenda": servicio.agenda(item.id, fecha),
            "horario": servicio.horario.describir(),
        }


class MisReservasView(LoginRequiredMixin, View):
    """Pantalla: menú "Mis reservas" → servicio.mis_reservas."""

    def get(self, request):
        servicio = _servicio()
        reservas = servicio.mis_reservas(request.user.id)
        items = _items_de(servicio, reservas)
        return render(request, "reservas/mis_reservas.html", {
            "filas": [(reserva, items.get(reserva.item_id)) for reserva in reservas],
            "es_supervisor": _tiene_rol(request.user, RolSistema.SUPERVISOR),
            "es_gestion": _tiene_rol(request.user, *ROLES_GESTION),
        })


class CancelarView(LoginRequiredMixin, View):
    """Botón "Cancelar" de Mis reservas → servicio.cancelar (solo el dueño)."""

    def post(self, request, pk):
        try:
            _servicio().cancelar(pk, request.user.id)
            messages.success(request, "Reserva cancelada.")
        except ValidationError as error:
            messages.error(request, _errores(error))
        return _volver(request, "reservas:mias")


class AgendaView(LoginRequiredMixin, View):
    """
    Pantalla: "Agenda" (enlace "Ver agenda" del detalle del ítem) → servicio.agenda.
    Muestra franjas ocupadas, lista de espera y horarios libres de un día.
    Los nombres de los solicitantes solo los ve el personal (Ley 29733).
    """

    def get(self, request, item_id):
        servicio = _servicio()
        item = _item_o_none(servicio, item_id)
        if item is None:
            messages.error(request, "El ítem no existe.")
            return redirect("catalogo:buscar")
        fecha = _fecha_pedida(request)
        agenda = servicio.agenda(item.id, fecha)
        nombres = self._nombres_visibles(request.user, agenda)
        return render(request, "reservas/agenda.html", {
            "item": item, "fecha": fecha, "agenda": agenda,
            "horario": servicio.horario.describir(),
            "ocupadas": [(r, nombres.get(r.solicitante_id, "Reservado")) for r in agenda["ocupadas"]],
            "cola": [(r, nombres.get(r.solicitante_id, "")) for r in agenda["cola"]],
            "es_gestion": _tiene_rol(request.user, *ROLES_GESTION),
            "form_motivo": MotivoForm(),
        })

    @staticmethod
    def _nombres_visibles(usuario, agenda):
        if not _tiene_rol(usuario, *ROLES_GESTION, RolSistema.SUPERVISOR):
            return {}
        return _nombres(r.solicitante_id for r in agenda["ocupadas"] + agenda["cola"])


class AnularView(RolRequeridoMixin, View):
    """Botón "Anular" de la agenda (ENCARGADO / ADMINISTRADOR) → servicio.anular."""
    roles_permitidos = list(ROLES_GESTION)

    def post(self, request, pk):
        form = MotivoForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Indica el motivo de la anulación.")
            return _volver(request, "reservas:mias")
        try:
            _servicio().anular(pk, request.user.id, form.cleaned_data["motivo"])
            messages.success(request, "Reserva anulada. Se avisó al solicitante.")
        except ValidationError as error:
            messages.error(request, _errores(error))
        return _volver(request, "reservas:mias")


class BandejaSupervisorView(RolRequeridoMixin, View):
    """Pantalla: "Bandeja del supervisor" (SUPERVISOR) → servicio.en_espera_supervisor."""
    roles_permitidos = [RolSistema.SUPERVISOR]

    def get(self, request):
        servicio = _servicio()
        pendientes = servicio.en_espera_supervisor()
        nombres = _nombres(r.solicitante_id for r in pendientes)
        items = _items_de(servicio, pendientes)
        return render(request, "reservas/bandeja_supervisor.html", {
            "filas": [(r, items.get(r.item_id), nombres.get(r.solicitante_id, "—")) for r in pendientes],
            "form_motivo": MotivoForm(),
        })


class AprobarSupervisorView(RolRequeridoMixin, View):
    """Botón "Aprobar" de la bandeja → servicio.aprobar_supervisor."""
    roles_permitidos = [RolSistema.SUPERVISOR]

    def post(self, request, pk):
        try:
            _servicio().aprobar_supervisor(pk, request.user.id)
            messages.success(request, "Reserva aprobada. Se avisó al solicitante.")
        except ValidationError as error:
            messages.error(request, _errores(error))
        return redirect("reservas:bandeja_supervisor")


class RechazarSupervisorView(RolRequeridoMixin, View):
    """Botón "Rechazar" de la bandeja (con motivo) → servicio.rechazar_supervisor."""
    roles_permitidos = [RolSistema.SUPERVISOR]

    def post(self, request, pk):
        form = MotivoForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Indica el motivo del rechazo.")
            return redirect("reservas:bandeja_supervisor")
        try:
            _servicio().rechazar_supervisor(pk, request.user.id, form.cleaned_data["motivo"])
            messages.success(request, "Reserva rechazada. Se avisó al solicitante.")
        except ValidationError as error:
            messages.error(request, _errores(error))
        return redirect("reservas:bandeja_supervisor")

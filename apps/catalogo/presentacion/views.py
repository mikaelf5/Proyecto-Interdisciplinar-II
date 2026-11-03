"""
Capa de PRESENTACIÓN — ItemController.

Cada vista: 1) lee la petición, 2) llama al servicio de aplicación, 3) muestra
el resultado. Nunca usa Item.objects ni otros modelos directamente.

Mapa rápido (pantalla → URL → vista → servicio):
    Buscar en el catálogo .. /catalogo/                  BuscarView          buscar_items
    Detalle del ítem ....... /catalogo/<id>/             DetalleView         obtener_item + historial_condicion
    Registrar ítem (admin) . /catalogo/nuevo/            RegistrarItemView   registrar_item
    Editar ítem (admin) .... /catalogo/<id>/editar/      EditarItemView      editar_item
    Poner disponible ....... /catalogo/<id>/disponible/  PonerDisponibleView cambiar_estado_item
    Marcar dañado .......... /catalogo/<id>/daniado/     MarcarDaniadoView   marcar_daniado
    Dar de baja ............ /catalogo/<id>/baja/        DarDeBajaView       dar_de_baja_item

Permisos por ROL (RolRequeridoMixin de Identidad):
    buscar y ver detalle → cualquier usuario con sesión;
    cambiar estado       → ENCARGADO o ADMINISTRADOR;
    registrar y editar   → ADMINISTRADOR.
"""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from apps.common.choices import EstadoItem, RolSistema
from apps.identidad.presentacion.permisos import RolRequeridoMixin

from ..aplicacion.dtos import EdicionItemDTO, FiltrosItem, NuevoItemDTO
from ..aplicacion.servicios import CatalogoServicioAplicacion
from .forms import FiltroItemForm, ItemNuevoForm

ROLES_GESTION = (RolSistema.ENCARGADO, RolSistema.ADMINISTRADOR)

catalogo = CatalogoServicioAplicacion()


def _errores(e):
    return " ".join(e.messages) if hasattr(e, "messages") else str(e)


def _tiene_rol(usuario, *roles):
    return usuario.is_superuser or usuario.tiene_algun_rol(*roles)


def _categoria(categoria_id):
    return next((c for c in catalogo.listar_categorias() if str(c.id) == str(categoria_id)), None)


def _codigo_escrito(form):
    return form.cleaned_data["codigo"].strip().upper()


def _mostrar_errores_en(form, error):
    for mensaje in error.messages:
        form.add_error(None, mensaje)


class BuscarView(LoginRequiredMixin, View):
    """Pantalla: menú "Catálogo" + botón "Buscar" → servicio.buscar_items (ItemController.buscar)."""

    def get(self, request):
        form = FiltroItemForm(request.GET or None, categorias=catalogo.listar_categorias())
        filtros = FiltrosItem()
        if form.is_valid():
            d = form.cleaned_data
            filtros = FiltrosItem(texto=d["texto"].strip(), categoria_id=d["categoria_id"] or None,
                                  estado=d["estado"])
        return render(request, "catalogo/item_list.html", {
            "form": form,
            "items": catalogo.buscar_items(filtros),
            "puede_registrar": _tiene_rol(request.user, RolSistema.ADMINISTRADOR),
        })


class RegistrarItemView(RolRequeridoMixin, View):
    """
    Pantalla: botón "+ Registrar ítem" (solo ADMINISTRADOR) → servicio.registrar_item.
    Paso 1 (GET): elegir la categoría. Paso 2 (POST): llenar sus atributos.
    """
    roles_permitidos = [RolSistema.ADMINISTRADOR]
    template_name = "catalogo/item_form.html"

    def get(self, request):
        categoria = _categoria(request.GET.get("categoria", ""))
        form = ItemNuevoForm(definicion=categoria.definicion_atributos) if categoria else None
        return render(request, self.template_name, self._contexto(categoria, form))

    def post(self, request):
        categoria = _categoria(request.POST.get("categoria", ""))
        if categoria is None:
            messages.error(request, "Elige una categoría.")
            return redirect("catalogo:registrar")
        form = ItemNuevoForm(request.POST, definicion=categoria.definicion_atributos)
        if form.is_valid():
            try:
                item = catalogo.registrar_item(NuevoItemDTO(
                    codigo=_codigo_escrito(form),
                    categoria_id=categoria.id,
                    atributos=form.atributos(),
                ))
                messages.success(request, f"Ítem {item.codigo} registrado.")
                return redirect("catalogo:detalle", pk=item.id)
            except ValidationError as e:
                _mostrar_errores_en(form, e)
        return render(request, self.template_name, self._contexto(categoria, form))

    @staticmethod
    def _contexto(categoria, form):
        return {"categorias": catalogo.listar_categorias(), "categoria": categoria, "form": form}


class EditarItemView(RolRequeridoMixin, View):
    """
    Pantalla: botón "Editar" del detalle (solo ADMINISTRADOR) → servicio.editar_item.
    Se corrigen el código y los atributos. La categoría no se cambia (de ella dependen
    los atributos y las políticas) y el estado se cambia con los botones del encargado.
    """
    roles_permitidos = [RolSistema.ADMINISTRADOR]
    template_name = "catalogo/item_editar.html"

    def get(self, request, pk):
        item = self._item(request, pk)
        if item is None:
            return redirect("catalogo:buscar")
        form = ItemNuevoForm(initial=ItemNuevoForm.valores_actuales(item), definicion=self._definicion(item))
        return render(request, self.template_name, {"item": item, "form": form})

    def post(self, request, pk):
        item = self._item(request, pk)
        if item is None:
            return redirect("catalogo:buscar")
        form = ItemNuevoForm(request.POST, definicion=self._definicion(item))
        if form.is_valid():
            try:
                catalogo.editar_item(EdicionItemDTO(item_id=item.id, codigo=_codigo_escrito(form),
                                                    atributos=form.atributos()))
                messages.success(request, "Cambios guardados.")
                return redirect("catalogo:detalle", pk=item.id)
            except ValidationError as e:
                _mostrar_errores_en(form, e)
        return render(request, self.template_name, {"item": item, "form": form})

    @staticmethod
    def _item(request, pk):
        """El ítem a editar; si no existe o está de baja, avisa y devuelve None."""
        try:
            item = catalogo.obtener_item(pk)
        except ValidationError as e:
            messages.error(request, _errores(e))
            return None
        if item.estado == EstadoItem.BAJA:
            messages.error(request, "Un ítem dado de baja ya no se puede editar.")
            return None
        return item

    @staticmethod
    def _definicion(item):
        return _categoria(item.categoria_id).definicion_atributos


class DetalleView(LoginRequiredMixin, View):
    """
    Pantalla: botón "Ver" del catálogo → servicio.obtener_item.
    También muestra la agenda de hoy (servicio de Reservas) y el historial de
    condición física (servicio.historial_condicion, RF-A5).
    """

    def get(self, request, pk):
        try:
            item = catalogo.obtener_item(pk)
        except ValidationError as e:
            messages.error(request, _errores(e))
            return redirect("catalogo:buscar")

        # Las reservas viven en otro contexto: se piden por SU servicio de aplicación.
        from apps.reservas.aplicacion.servicios import ReservaServicioAplicacion
        hoy = timezone.localdate()
        agenda = ReservaServicioAplicacion().agenda(pk, hoy)

        historial = catalogo.historial_condicion(pk)
        responsables = {c.pk: c.nombres for c in get_user_model().objects.filter(
            pk__in={h.responsable_id for h in historial})}

        return render(request, "catalogo/item_detail.html", {
            "item": item,
            "hoy": hoy,
            "agenda": agenda,
            "historial": [(h, responsables.get(h.responsable_id, "—")) for h in historial],
            "puede_gestionar": _tiene_rol(request.user, *ROLES_GESTION),
            "puede_editar": _tiene_rol(request.user, RolSistema.ADMINISTRADOR) and item.estado != EstadoItem.BAJA,
            "puede_reservar": _tiene_rol(request.user, RolSistema.SOLICITANTE),
            "fuera_de_servicio": item.estado in (EstadoItem.BAJA, EstadoItem.MANTENIMIENTO),
        })


class _AccionEncargadoView(RolRequeridoMixin, View):
    """Base de las acciones del encargado: solo POST, solo ENCARGADO/ADMINISTRADOR."""
    roles_permitidos = list(ROLES_GESTION)
    mensaje_ok = ""

    def ejecutar(self, request, pk):
        raise NotImplementedError

    def post(self, request, pk):
        try:
            self.ejecutar(request, pk)
            messages.success(request, self.mensaje_ok)
        except ValidationError as e:
            messages.error(request, _errores(e))
        return redirect("catalogo:detalle", pk=pk)


class PonerDisponibleView(_AccionEncargadoView):
    """Botón "Poner disponible" → servicio.cambiar_estado_item (ItemController.cambiarEstado)."""
    mensaje_ok = "El ítem quedó disponible."

    def ejecutar(self, request, pk):
        catalogo.cambiar_estado_item(pk, EstadoItem.DISPONIBLE)


class MarcarDaniadoView(_AccionEncargadoView):
    """Botón "Marcar dañado" (con motivo) → servicio.marcar_daniado (ItemController.marcarDaniado)."""
    mensaje_ok = "El ítem pasó a mantenimiento. Sus reservas futuras se anularon y se avisó a cada solicitante."

    def ejecutar(self, request, pk):
        catalogo.marcar_daniado(pk, request.POST.get("motivo", ""))


class DarDeBajaView(_AccionEncargadoView):
    """Botón "Dar de baja" (con motivo) → servicio.dar_de_baja_item."""
    mensaje_ok = "El ítem fue dado de baja. Sus reservas futuras se anularon y se avisó a cada solicitante."

    def ejecutar(self, request, pk):
        catalogo.dar_de_baja_item(pk, request.POST.get("motivo", ""))

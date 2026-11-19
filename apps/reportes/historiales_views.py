"""Pantallas de historial (RF de la observación de la docente).

- Historial de una persona: el Administrador y el Encargado ven el de cualquiera;
  cualquier otro usuario solo puede ver el suyo.
- Historial de un ítem: solo el Administrador y el Encargado.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView

from apps.auditoria.utils import actor_id_de
from apps.common.choices import RolSistema
from apps.identidad.presentacion.permisos import RolRequeridoMixin

from .aplicacion.historiales import HistorialNoEncontrado
from .dominio.exportador import FORMATOS
from .fabrica import historial_servicio

ROLES_QUE_VEN_TODO = (RolSistema.ADMINISTRADOR, RolSistema.ENCARGADO)


def ve_todos_los_historiales(usuario):
    return usuario.is_superuser or usuario.tiene_algun_rol(*ROLES_QUE_VEN_TODO)


def _puede_ver_persona(usuario, cuenta_id):
    return ve_todos_los_historiales(usuario) or usuario.pk == cuenta_id


def _descarga(contenido, content_type, nombre):
    respuesta = HttpResponse(contenido, content_type=content_type)
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return respuesta


def _grafico(datos):
    g = datos.grafico
    if g and any(g.valores):
        return {"tipo": g.tipo, "titulo": g.titulo, "etiquetas": g.etiquetas, "valores": g.valores}
    return None


# ---------------------------------------------------------------------------
# Persona
# ---------------------------------------------------------------------------
class BuscarPersonaView(LoginRequiredMixin, TemplateView):
    """Buscar a quién ver. Quien no es personal va directo a su propio historial."""

    template_name = "reportes/historial_buscar_persona.html"

    def get(self, request, *args, **kwargs):
        if not ve_todos_los_historiales(request.user):
            return redirect("reportes:historial_persona", request.user.pk)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = self.request.GET.get("q", "")
        ctx.update(q=q, resultados=historial_servicio().buscar_personas(q))
        return ctx


class HistorialPersonaView(LoginRequiredMixin, TemplateView):
    template_name = "reportes/historial_detalle.html"

    def get(self, request, *args, **kwargs):
        if not _puede_ver_persona(request.user, kwargs["cuenta_id"]):
            raise PermissionDenied
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cuenta_id = self.kwargs["cuenta_id"]
        try:
            datos = historial_servicio().de_persona(cuenta_id, pedido_por_id=self.request.user.pk)
        except HistorialNoEncontrado:
            raise Http404("La persona no existe.")
        ctx.update(
            datos=datos, grafico=_grafico(datos), tipo="persona", objeto_id=cuenta_id,
            ve_todo=ve_todos_los_historiales(self.request.user),
            es_propio=self.request.user.pk == cuenta_id,
        )
        return ctx


def exportar_historial_persona(request, cuenta_id, formato):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    if not _puede_ver_persona(request.user, cuenta_id):
        raise PermissionDenied
    if formato not in FORMATOS:
        raise Http404("Formato no soportado")
    try:
        return _descarga(*historial_servicio().exportar_persona(cuenta_id, formato, actor_id_de(request)))
    except HistorialNoEncontrado:
        raise Http404("La persona no existe.")


# ---------------------------------------------------------------------------
# Ítem
# ---------------------------------------------------------------------------
class _SoloPersonal(RolRequeridoMixin):
    roles_permitidos = list(ROLES_QUE_VEN_TODO)


class BuscarItemView(_SoloPersonal, TemplateView):
    template_name = "reportes/historial_buscar_item.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = self.request.GET.get("q", "")
        ctx.update(q=q, resultados=historial_servicio().buscar_items(q))
        return ctx


class HistorialItemView(_SoloPersonal, TemplateView):
    template_name = "reportes/historial_detalle.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        item_id = self.kwargs["item_id"]
        try:
            datos = historial_servicio().de_item(item_id, pedido_por_id=self.request.user.pk)
        except HistorialNoEncontrado:
            raise Http404("El ítem no existe.")
        ctx.update(datos=datos, grafico=_grafico(datos), tipo="item", objeto_id=item_id, ve_todo=True)
        return ctx


def exportar_historial_item(request, item_id, formato):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    if not ve_todos_los_historiales(request.user):
        raise PermissionDenied
    if formato not in FORMATOS:
        raise Http404("Formato no soportado")
    try:
        return _descarga(*historial_servicio().exportar_item(item_id, formato, actor_id_de(request)))
    except HistorialNoEncontrado:
        raise Http404("El ítem no existe.")

"""
Capa de PRESENTACIÓN — ItemController (PDF).

Las vistas solo:
    1. leen la petición (request),
    2. llaman al servicio de aplicación,
    3. muestran el resultado o el error.
Nunca usan Item.objects ni otros modelos directamente.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.common.choices import EstadoItem, RolSistema

from ..aplicacion.dtos import FiltrosItem, NuevoItemDTO
from ..aplicacion.servicios import CatalogoServicioAplicacion
from .forms import FiltroItemForm, ItemForm

catalogo = CatalogoServicioAplicacion()

# Solo el personal (encargados/admin) cambia el estado de los ítems.
# Cuando Identidad tenga permisos por rol, se reemplaza por el rol ENCARGADO.
solo_personal = user_passes_test(lambda u: u.is_staff)

def es_administrador(usuario):
    """Superusuario o cuenta con el rol ADMINISTRADOR (RF-B5)."""
    return usuario.is_authenticated and (
        usuario.is_superuser or usuario.tiene_rol(RolSistema.ADMINISTRADOR)
    )


def solo_admin(vista):
    """Si la cuenta no es administradora responde 403 (no la manda al login)."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not es_administrador(request.user):
            raise PermissionDenied("Solo el administrador puede registrar ítems.")
        return vista(request, *args, **kwargs)
    return envoltura



def _errores(e):
    return " ".join(e.messages) if hasattr(e, "messages") else str(e)


@login_required
def buscar(request):
    """ItemController.buscar(request)"""
    form = FiltroItemForm(request.GET or None, categorias=catalogo.listar_categorias())
    filtros = FiltrosItem()
    if form.is_valid():
        d = form.cleaned_data
        filtros = FiltrosItem(texto=d["texto"].strip(), categoria_id=d["categoria_id"] or None,
                              estado=d["estado"])
    return render(request, "catalogo/item_list.html", {
        "form": form,
        "items": catalogo.buscar_items(filtros),
        "puede_registrar": es_administrador(request.user),
    })


@login_required
@solo_admin
def registrar(request):
    """ItemController.registrar(request): el administrador sube un ítem nuevo."""
    categorias = catalogo.listar_categorias()
    form = ItemForm(request.POST or None, categorias=categorias)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        dto = NuevoItemDTO(codigo=d["codigo"], categoria_id=d["categoria_id"],atributos=d["atributos"])
        try:
            item = catalogo.registrar_item(dto)
        except ValidationError as e:
            form.add_error(None, _errores(e))
        else:
            messages.success(request, f"Ítem {item.codigo} registrado.")
            return redirect("catalogo:detalle", pk=item.id)
    return render(request, "catalogo/item_form.html", {
        "form": form,
        "hay_categorias": bool(categorias),
    })

@login_required
def detalle(request, pk):
    try:
        item = catalogo.obtener_item(pk)
    except ValidationError as e:
        messages.error(request, _errores(e))
        return redirect("catalogo:buscar")

    # La cola de espera vive en otro contexto (Reservas): se pide por SU servicio de aplicación.
    from apps.reservas.aplicacion.servicios import ReservaServicioAplicacion
    cola = ReservaServicioAplicacion().lista_espera(pk)

    return render(request, "catalogo/item_detail.html", {
        "item": item,
        "cola": cola,
        "estados": EstadoItem,
    })


def _accion(request, pk, funcion, ok):
    try:
        funcion()
        messages.success(request, ok)
    except ValidationError as e:
        messages.error(request, _errores(e))
    return redirect("catalogo:detalle", pk=pk)


@login_required
@solo_personal
@require_POST
def poner_disponible(request, pk):
    """ItemController.cambiarEstado(request, id)"""
    return _accion(request, pk, lambda: catalogo.cambiar_estado_item(pk, EstadoItem.DISPONIBLE),
                   "El ítem quedó disponible.")


@login_required
@solo_personal
@require_POST
def marcar_daniado(request, pk):
    """ItemController.marcarDaniado(request, id)"""
    return _accion(request, pk, lambda: catalogo.marcar_daniado(pk, request.POST.get("motivo", "")),
                   "El ítem pasó a mantenimiento.")


@login_required
@solo_personal
@require_POST
def dar_de_baja(request, pk):
    return _accion(request, pk, lambda: catalogo.dar_de_baja_item(pk, request.POST.get("motivo", "")),
                   "El ítem fue dado de baja.")

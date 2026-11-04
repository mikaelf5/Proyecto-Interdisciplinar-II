"""Vistas HTTP de Circulación: autorización en servidor y comandos por POST."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView
from apps.identidad.presentacion.permisos import RolRequeridoMixin

from apps.common.choices import (
    RolSistema,
    EstadoPrestamo,
    EstadoReserva,
)

from apps.circulacion.presentacion.forms import (
    EntregaPrestamoForm,
    DevolucionForm,
    RenovarPrestamoForm,
)

from apps.circulacion.aplicacion.dtos import (
    EntregaPrestamoDTO,
    DevolucionDTO,
)

from apps.circulacion.fabrica import prestamo_servicio
class EntregasHoyView(RolRequeridoMixin, ListView):
    roles_permitidos = [RolSistema.ENCARGADO]
    template_name = "circulacion/entregas_hoy.html"
    context_object_name = "reservas"



    def get_queryset(self):
        servicio = prestamo_servicio()
        catalogo = servicio.catalogo
        identidad = servicio.identidad

        reservas = servicio.reservas.confirmadas_de_hoy()
        resultado = []

        for reserva in reservas:
            item = catalogo.obtener_item(reserva.item_id)
            solicitante = identidad.obtener_cuenta(reserva.solicitante_id)

            resultado.append({
                "reserva": reserva,
                "item": item,
                "solicitante": solicitante,
            })

        return resultado

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        servicio = prestamo_servicio()
        catalogo = servicio.catalogo
        identidad = servicio.identidad

        prestamos = servicio.entregados_hoy()
        resultado = []

        for prestamo in prestamos:
            item = catalogo.obtener_item(prestamo.item_id)
            solicitante = identidad.obtener_cuenta(prestamo.solicitante_id)

            resultado.append({
                "prestamo": prestamo,
                "item": item,
                "solicitante": solicitante,
            })

        context["prestamos_realizados"] = resultado

        return context
class RegistrarEntregaView(RolRequeridoMixin, View):
    roles_permitidos = [RolSistema.ENCARGADO]

    http_method_names = ["get", "post", "options"]

    def get(self, request, reserva_id):
        servicio = prestamo_servicio()

        try:
            reserva = servicio.reservas.obtener(reserva_id)
        except ValidationError:
            messages.error(request, "No se encontró la reserva.")
            return redirect("circulacion:entregas_hoy")

        if reserva.estado != EstadoReserva.CONFIRMADA:
            messages.error(
                request,
                "Esta reserva ya no está pendiente de entrega."
            )
            return redirect("circulacion:entregas_hoy")

        form = EntregaPrestamoForm()

        return render(
            request,
            "circulacion/registrar_entrega.html",
            {
                "form": form,
                "reserva": reserva,
            }
        )

    def post(self, request, reserva_id):
        form = EntregaPrestamoForm(request.POST)

        if form.is_valid():
            datos = form.cleaned_data

            dto = EntregaPrestamoDTO(
                reserva_id=reserva_id,
                encargado_id=request.user.id,
                garantia_tipo=datos["garantia_tipo"],
                garantia_detalle=datos["garantia_detalle"],
                terminos_aceptados=datos["terminos_aceptados"],
                descripcion_condicion=datos["descripcion_condicion"],
            )

            try:
                prestamo_servicio().registrar_entrega(dto)

            except ValidationError as error:
                form.add_error(None, error)

            else:
                messages.success(
                    request,
                    "La entrega se registró correctamente."
                )
                return redirect("circulacion:entregas_hoy")

        servicio = prestamo_servicio()

        try:
            reserva = servicio.reservas.obtener(reserva_id)
        except ValidationError:
            messages.error(request, "No se encontró la reserva.")
            return redirect("circulacion:entregas_hoy")

        return render(
            request,
            "circulacion/registrar_entrega.html",
            {
                "form": form,
                "reserva": reserva,
            }
        )
class DevolucionesView(RolRequeridoMixin, ListView):
    roles_permitidos = [RolSistema.ENCARGADO]

    template_name = "circulacion/devoluciones.html"
    context_object_name = "prestamos"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.tiene_rol(RolSistema.ENCARGADO):
            raise PermissionDenied("Se requiere el rol Encargado.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        servicio = prestamo_servicio()
        resultado = []

        for prestamo in servicio.abiertos():
            item = servicio.catalogo.obtener_item(prestamo.item_id)
            solicitante = servicio.identidad.obtener_cuenta(
                prestamo.solicitante_id
            )

            nombre_articulo = (
                f"{item.codigo} — "
                f"{item.atributos.get('marca', '')} "
                f"{item.atributos.get('modelo', '')}"
            ).strip()

            resultado.append({
                "prestamo": prestamo,
                "articulo": nombre_articulo,
                "solicitante": solicitante,
            })

        return resultado


class RegistrarDevolucionView(RolRequeridoMixin, View):
    roles_permitidos = [RolSistema.ENCARGADO]

    http_method_names = ["get", "post", "options"]

    def obtener_prestamo(self, prestamo_id):
        servicio = prestamo_servicio()

        prestamo = next(
            (
                p for p in servicio.abiertos()
                if p.id == prestamo_id
            ),
            None
        )

        return servicio, prestamo

    def get(self, request, prestamo_id):
        servicio, prestamo = self.obtener_prestamo(prestamo_id)

        if prestamo is None:
            messages.error(request, "No se encontró un préstamo abierto.")
            return redirect("circulacion:devoluciones")

        item = servicio.catalogo.obtener_item(prestamo.item_id)
        solicitante = servicio.identidad.obtener_cuenta(
            prestamo.solicitante_id
        )

        return render(
            request,
            "circulacion/registrar_devolucion.html",
            {
                "form": DevolucionForm(),
                "prestamo": prestamo,
                "item": item,
                "solicitante": solicitante,
            }
        )

    def post(self, request, prestamo_id):
        form = DevolucionForm(request.POST)

        if form.is_valid():
            datos = form.cleaned_data

            dto = DevolucionDTO(
                prestamo_id=prestamo_id,
                encargado_id=request.user.id,
                descripcion_condicion=datos["descripcion_condicion"],
                garantia_devuelta=datos["garantia_devuelta"],
                item_daniado=datos["item_daniado"],
            )

            try:
                prestamo_servicio().registrar_devolucion(dto)

            except ValidationError as error:
                form.add_error(None, error)

            else:
                messages.success(
                    request,
                    "La devolución se registró correctamente."
                )
                return redirect("circulacion:devoluciones")

        servicio, prestamo = self.obtener_prestamo(prestamo_id)

        if prestamo is None:
            messages.error(request, "No se encontró un préstamo abierto.")
            return redirect("circulacion:devoluciones")

        item = servicio.catalogo.obtener_item(prestamo.item_id)
        solicitante = servicio.identidad.obtener_cuenta(
            prestamo.solicitante_id
        )

        return render(
            request,
            "circulacion/registrar_devolucion.html",
            {
                "form": form,
                "prestamo": prestamo,
                "item": item,
                "solicitante": solicitante,
            }
        )


class MisPrestamosView(LoginRequiredMixin, ListView):
    template_name = "circulacion/mis_prestamos.html"
    context_object_name = "prestamos"

    def get_queryset(self):
        servicio = prestamo_servicio()
        historial = servicio.historial_de(self.request.user.id)

        resultado = []

        for prestamo in historial:
            item = servicio.catalogo.obtener_item(prestamo.item_id)

            nombre_articulo = (
                f"{item.codigo} — "
                f"{item.atributos.get('marca', '')} "
                f"{item.atributos.get('modelo', '')}"
            ).strip()

            puede_renovar = (
                prestamo.estado == EstadoPrestamo.ACTIVO
                or prestamo.estado == EstadoPrestamo.ACTIVO.value
            )

            resultado.append({
                "prestamo": prestamo,
                "articulo": nombre_articulo,
                "puede_renovar": puede_renovar,
            })

        return resultado


class RenovarPrestamoView(LoginRequiredMixin, View):
    http_method_names = ["get", "post", "options"]

    def obtener_prestamo(self, request, prestamo_id):
        servicio = prestamo_servicio()

        historial = servicio.historial_de(request.user.id)

        prestamo = next(
            (p for p in historial if p.id == prestamo_id),
            None
        )

        if prestamo is None:
            raise PermissionDenied(
                "No tienes autorización para renovar este préstamo."
            )

        return servicio, prestamo

    def get(self, request, prestamo_id):
        servicio, prestamo = self.obtener_prestamo(
            request, prestamo_id
        )

        if prestamo.estado != EstadoPrestamo.ACTIVO:
            messages.error(request, "Este préstamo no está activo.")
            return redirect("circulacion:mis_prestamos")

        try:
            reserva = servicio.reservas.obtener(prestamo.reserva_id)
        except ValidationError:
            messages.error(request, "No se encontró la reserva asociada.")
            return redirect("circulacion:mis_prestamos")

        item = servicio.catalogo.obtener_item(prestamo.item_id)

        return render(
            request,
            "circulacion/renovar_prestamo.html",
            {
                "prestamo": prestamo,
                "reserva": reserva,
                "item": item,
                "form": RenovarPrestamoForm(),
            }
        )

    def post(self, request, prestamo_id):
        servicio, prestamo = self.obtener_prestamo(
            request, prestamo_id
        )

        form = RenovarPrestamoForm(request.POST)

        if form.is_valid():
            try:
                servicio.renovar(
                    prestamo_id,
                    form.cleaned_data["nueva_hora_fin"]
                )

            except ValidationError as error:
                messages.error(request, "; ".join(error.messages))

            else:
                messages.success(
                    request,
                    "El préstamo se renovó correctamente."
                )

                return redirect("circulacion:mis_prestamos")

        try:
            reserva = servicio.reservas.obtener(prestamo.reserva_id)
        except ValidationError:
            messages.error(request, "No se encontró la reserva asociada.")
            return redirect("circulacion:mis_prestamos")

        item = servicio.catalogo.obtener_item(prestamo.item_id)

        return render(
            request,
            "circulacion/renovar_prestamo.html",
            {
                "prestamo": prestamo,
                "reserva": reserva,
                "item": item,
                "form": form,
            }
        )
class PrestamosVencidosView(RolRequeridoMixin, ListView):
    roles_permitidos = [RolSistema.ENCARGADO]

    template_name = "circulacion/prestamos_vencidos.html"
    context_object_name = "prestamos"

    def get_queryset(self):
        servicio = prestamo_servicio()
        resultado = []

        # Obtener el texto ingresado en el buscador.
        busqueda = self.request.GET.get("q", "").strip().lower()

        ahora = timezone.now()

        for prestamo in servicio.listar_vencidos():
            item = servicio.catalogo.obtener_item(prestamo.item_id)
            solicitante = servicio.identidad.obtener_cuenta(
                prestamo.solicitante_id
            )

            nombre_articulo = (
                f"{item.codigo} — "
                f"{item.atributos.get('marca', '')} "
                f"{item.atributos.get('modelo', '')}"
            ).strip()

            # Filtrar por artículo o por los datos del solicitante.
            if busqueda:
                texto_articulo = nombre_articulo.lower()
                texto_solicitante = (
                    f"{solicitante.nombres} "
                    f"{solicitante.dni} "
                    f"{solicitante.correo}"
                ).lower()

                if (
                    busqueda not in texto_articulo
                    and busqueda not in texto_solicitante
                ):
                    continue

            tiempo_vencido = ahora - prestamo.fecha_vencimiento

            nombre_solicitante = (
                f"{solicitante.nombres} — DNI: {solicitante.dni}"
            )

            resultado.append({
                "prestamo": prestamo,
                "articulo": nombre_articulo,
                "solicitante": nombre_solicitante,
                "tiempo_vencido": tiempo_vencido,
            })

        return resultado
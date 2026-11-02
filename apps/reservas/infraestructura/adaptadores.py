"""
Capa de INFRAESTRUCTURA — adaptadores hacia otros contextos.

Implementan los puertos de dominio/puertos.py llamando a los SERVICIOS de
Identidad y Políticas (nunca a sus tablas desde la lógica de Reservas).

Mientras Natalie publica `tipo_usuario_de` y Marving `politica_para`, el
adaptador usa lo que ya existe en esos módulos (perfil del solicitante y
`buscar_por_categoria`). Cuando lo publiquen, se usa automáticamente.
"""
from ..dominio.puertos import IIdentidadPuerto, IPoliticasPuerto


class IdentidadAdaptador(IIdentidadPuerto):
    def __init__(self):
        from apps.identidad.fabrica import cuenta_servicio
        self._servicio = cuenta_servicio()

    def habilitacion(self, cuenta_id):
        resultado = self._servicio.consultar_habilitacion(cuenta_id)
        return bool(resultado), resultado.mensaje

    def tipo_usuario(self, cuenta_id):
        publicado = getattr(self._servicio, "tipo_usuario_de", None)
        if callable(publicado):
            return publicado(cuenta_id)
        from apps.identidad.infraestructura.repositorio_django import PerfilSolicitanteRepositorioImpl
        perfil = PerfilSolicitanteRepositorioImpl().de_cuenta(cuenta_id)
        return perfil.tipo if perfil else None


class PoliticasAdaptador(IPoliticasPuerto):
    def __init__(self):
        from apps.politicas.aplicacion.servicios import PoliticaServicioAplicacion
        from apps.politicas.infraestructura.repositorio_django import PoliticaRepositorioImpl
        self._servicio = PoliticaServicioAplicacion(PoliticaRepositorioImpl())

    def politica_para(self, categoria_id, tipo_usuario):
        publicado = getattr(self._servicio, "politica_para", None)
        if callable(publicado):
            return publicado(categoria_id, tipo_usuario)
        return self._servicio.obtener_por_categoria(categoria_id, tipo_usuario)

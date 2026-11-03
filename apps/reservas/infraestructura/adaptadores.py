"""
Capa de INFRAESTRUCTURA — adaptadores hacia otros contextos.

Implementan los puertos de dominio/puertos.py llamando a los SERVICIOS de
Identidad y Políticas (nunca a sus tablas desde la lógica de Reservas).

Mientras Natalie publica `tipo_usuario_de` y Marving `politica_para`, el
adaptador usa lo que ya existe en esos módulos (perfil del solicitante y
`buscar_por_categoria`). Cuando lo publiquen, se usa automáticamente.
"""
from ..dominio.puertos import IIdentidadPuerto, IPoliticasPuerto
from ..dominio.politicas import politica_por_defecto


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
        """Primero la que configuró el administrador (base de datos); si no hay, la del código."""
        return self._politica_configurada(categoria_id, tipo_usuario) or self._politica_del_codigo(categoria_id, tipo_usuario)

    def _politica_configurada(self, categoria_id, tipo_usuario):
        publicado = getattr(self._servicio, "politica_para", None)
        if callable(publicado):
            return publicado(categoria_id, tipo_usuario)
        return self._servicio.obtener_por_categoria(categoria_id, tipo_usuario)

    @staticmethod
    def _politica_del_codigo(categoria_id, tipo_usuario):
        from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
        categoria = next((c for c in CatalogoServicioAplicacion().listar_categorias()
                          if str(c.id) == str(categoria_id)), None)
        if categoria is None:
            return None
        return politica_por_defecto(categoria.nombre, categoria.es_especial, tipo_usuario)

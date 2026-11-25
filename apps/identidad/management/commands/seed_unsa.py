"""
Carga los USUARIOS REALES del curso (alumnos, docentes y administrativos de la
escuela) con datos personales FICTICIOS pero FIJOS.

Uso:
    python manage.py seed_unsa

¿Por qué existe? La profesora pidió que los 4 tengamos los MISMOS datos en
nuestra base local. Por eso los DNI, CUI, celulares y direcciones están
escritos aquí tal cual (no se generan al azar al correr): quien lo ejecute
obtiene exactamente las mismas 55 cuentas.

- Se puede correr varias veces: si la cuenta ya existe (mismo correo), la deja
  como dice este archivo (nombres, DNI, contacto, roles, perfil y contraseña).
- Todo o nada: si una cuenta falla, no se guarda ninguna.
- Las cuentas nuevas se crean con el caso de uso `registrar_cuenta`, igual que
  la pantalla «Registrar usuario» (acta + consentimiento incluidos).
- Convive con `seed_demo` / `seed_cuentas` (cuentas @demo.pe): no las toca.

Correo institucional = 1.ª letra del primer nombre + apellido paterno
+ 1.ª letra del apellido materno, en minúsculas, sin tildes ni espacios:
    Natalie Marleny Lazo Paxi  ->  nlazop@unsa.edu.pe

DNI, CUI, celular y dirección son INVENTADOS (no son los datos reales de nadie).
"""
import unicodedata

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.common.choices import RolSistema, TipoUsuario
from apps.identidad.aplicacion.dtos import PerfilSolicitanteDTO, RegistroCuentaDTO
from apps.identidad.aplicacion.servicios import ACTOR_SISTEMA
from apps.identidad.dominio.documentos import VERSION_ACTA, VERSION_CONSENTIMIENTO
from apps.identidad.dominio.excepciones import DatosInvalidos
from apps.identidad.fabrica import cuenta_servicio
from apps.identidad.models import Cuenta, PerfilSolicitante

CLAVE = "unsa2026"
DOMINIO = "@unsa.edu.pe"

# (nombres, apellido paterno, apellido materno, DNI, CUI, celular, dirección)
# Fuente de los nombres: lista de participantes del aula virtual (26B · OTI).
ALUMNOS = [
    ("Jesus Alberto", "Alfaro", "Buiza", "71999250", "20238233", "968695681", "Av. Goyeneche 328, Socabaya"),
    ("Marco Antonio", "Armendariz", "Paredes", "76213386", "20236891", "976848884", "Av. Kennedy 869, Socabaya"),
    ("Albert Gussepe", "Blanco", "Cana", "74700173", "20220041", "982437103", "Calle San Juan de Dios 213, Paucarpata"),
    ("Karina Paola", "Calcina", "Chuquipalla", "77851490", "20217367", "901542004", "Av. Kennedy 795, Miraflores"),
    ("Diego", "Canqui", "Ecos", "72763492", "20234120", "946661846", "Av. Venezuela 924, Cerro Colorado"),
    ("Anderson Samuel", "Carpio", "Chura", "77257649", "20231250", "997054446", "Calle Ugarte 191, Mariano Melgar"),
    ("Moises Robert", "Ccaso", "Idme", "75513614", "20234712", "961397604", "Calle Bolívar 997, Hunter"),
    ("Elyud Edgar", "Chayña", "Calcina", "76905374", "20249460", "941473104", "Calle Mercaderes 968, Alto Selva Alegre"),
    ("Luis Antonio", "Chipana", "Chura", "74094092", "20237554", "956669073", "Calle San Juan de Dios 508, Socabaya"),
    ("Aldair Daniel", "Condori", "Ataucuri", "75651055", "20231907", "957102035", "Av. Kennedy 507, Mariano Melgar"),
    ("Emilio Alejandro", "Condori", "Pallardel", "73169658", "20239240", "964315788", "Calle Mercaderes 689, José Luis Bustamante y Rivero"),
    ("Stephano Gian Pierre", "Delgado", "Chavez", "77424216", "20220800", "994578218", "Av. Goyeneche 834, Socabaya"),
    ("Mauricio Alejandro", "Farfan", "Huayta", "74602148", "20232333", "964708126", "Av. Independencia 970, Yanahuara"),
    ("Fernando Antonio", "Gama", "Llicahua", "76256893", "20247484", "990503438", "Av. Kennedy 831, Mariano Melgar"),
    ("Carlos Enrique", "Gutierrez", "Castilla", "73105594", "20236587", "989892850", "Av. Lambramani 661, Hunter"),
    ("Johan Diego", "Huamani", "Sabina", "75210239", "20247846", "953948553", "Av. Parra 307, Paucarpata"),
    ("Estrella de Jesús Emilia Fabiana", "Huarsaya", "Márquez", "77977996", "20230151", "904443850", "Calle Bolívar 771, Socabaya"),
    ("Lizzy Arlette", "Huayhua", "Perez", "74843890", "20238020", "948309773", "Calle Jerusalén 366, Alto Selva Alegre"),
    ("Roid Niro", "Huaylla", "Guzman", "75073249", "20238376", "966727300", "Av. Parra 671, Hunter"),
    ("Daysi", "Jara", "Arisaca", "78610700", "20214752", "942500997", "Calle Moral 931, Yanahuara"),
    ("Hellen Grace", "Juan de Dios", "Delgado", "74677993", "20248440", "934739729", "Calle Moral 287, Cerro Colorado"),
    ("Natalie Marleny", "Lazo", "Paxi", "78066897", "20247850", "908629549", "Calle Puente Grau 610, Miraflores"),
    ("Fernando Enrique", "Llosa", "Manchego", "71810864", "20226738", "919643929", "Calle Moral 114, Yanahuara"),
    ("Mariana Valery", "Luis", "Jimenez", "71001794", "20239513", "973362139", "Calle San Juan de Dios 724, José Luis Bustamante y Rivero"),
    ("Diego de Alessandro", "Mamani", "Salazar", "73079012", "20210731", "973343091", "Calle Puente Grau 784, Hunter"),
    ("Luis Fernando", "Morales", "Tacca", "73996835", "20220084", "942069571", "Av. Kennedy 806, Alto Selva Alegre"),
    ("Neill Elverth", "Olazabal", "Chavez", "78864433", "20228942", "929920845", "Av. Kennedy 702, Cayma"),
    ("Alvaro Johan", "Panibra", "Choctaya", "76017531", "20248269", "939014429", "Calle San Juan de Dios 527, Hunter"),
    ("Javier Alonzo", "Peñalva", "Humire", "72343196", "20229601", "941071205", "Av. Parra 499, Cayma"),
    ("Jesus Gustavo", "Perez", "Villasante", "75362335", "20226160", "901896747", "Av. Goyeneche 498, Yanahuara"),
    ("Juan Carlos", "Postigo", "Cabana", "71430967", "20235790", "903461507", "Calle Mercaderes 622, Sachaca"),
    ("Claudia Roxana", "Quisocala", "Cruz", "73749450", "20244975", "960416819", "Calle Ugarte 224, Sachaca"),
    ("Sharmely Yesenia", "Quispe", "Chavez", "78958961", "20239365", "983027895", "Av. Dolores 257, Socabaya"),
    ("David Augusto", "Quispe", "Lloccallasi", "75358835", "20227104", "983663689", "Calle Ugarte 569, Socabaya"),
    ("Angelo Josue", "Quispe", "Suarez", "72957284", "20241138", "973464604", "Calle Santo Domingo 134, José Luis Bustamante y Rivero"),
    ("Job Lorenzo", "Quispe", "Torrez", "76429362", "20220741", "987004064", "Av. Ejército 562, Hunter"),
    ("Luis Enrique", "Ramos", "Chambi", "72581498", "20230335", "917332847", "Calle Jerusalén 904, Mariano Melgar"),
    ("Rodrigo Abraham", "Ramos", "Mamani", "78504580", "20222627", "988747837", "Av. Dolores 499, Paucarpata"),
    ("Omar Joaquin", "Rivera", "Olivera", "74568130", "20236784", "910557407", "Calle Santo Domingo 412, Cayma"),
    ("Edu Andre", "Sucari", "Ccansaya", "73886234", "20224316", "962265651", "Av. Kennedy 898, Cerro Colorado"),
    ("Cristhian Luis", "Taipe", "Huanca", "73413153", "20232899", "943726695", "Av. Kennedy 555, Yanahuara"),
    ("Lizeth Angelica", "Tito", "Vilca", "75422909", "20234486", "912692439", "Calle Jerusalén 336, Cercado"),
    ("Jhair Alejandro", "Torres", "Chavez", "78999996", "20217440", "986661596", "Calle Ugarte 517, Mariano Melgar"),
    ("Micaela Belen", "Uribe", "Zuñiga", "77570912", "20242989", "903648678", "Av. Venezuela 966, Cayma"),
    ("Ronald Reynaldo", "Valdez", "Agüero", "73950287", "20239377", "972259971", "Calle Jerusalén 212, Socabaya"),
    ("Diego Mauricio", "Villanueva", "Flores", "77006348", "20239106", "976241241", "Calle Jerusalén 683, Paucarpata"),
    ("Marving Alonzo", "Zamata", "Huaracha", "75721371", "20239105", "917799708", "Av. Goyeneche 900, Paucarpata"),
    ("Eduardo Josue", "Zela", "Quispe", "71808919", "20232806", "914231875", "Av. Ejército 877, Miraflores"),
]
DOCENTES = [
    ("Yessenia Deysi", "Yari", "Ramos", "29857447", "", "924896742", "Av. Goyeneche 618, Miraflores"),
    ("Ana Maria", "Cuadros", "Valdivia", "29390231", "", "978934594", "Calle San Juan de Dios 398, Miraflores"),
    ("Edgar", "Sarmiento", "Calisaya", "29269230", "", "935011808", "Calle Puente Grau 164, Cercado"),
    ("Rolando Jesus", "Cardenas", "Talavera", "29531638", "", "934499597", "Av. Parra 115, Cercado"),
    ("Alfredo", "Paz", "Valderrama", "29201135", "", "931571416", "Calle Mercaderes 417, Yanahuara"),
]
ADMINISTRATIVOS = [
    ("Raquel Consuelo", "Argüelles", "Flórez", "29198429", "", "992050076", "Av. Venezuela 422, Sachaca"),
    ("Juan Carlos", "Gutierrez", "Caceres", "29736753", "", "983983744", "Av. Ejército 513, Miraflores"),
]

# Roles extra de algunas personas (correo -> roles). Todos los demás son solo
# SOLICITANTE. Cámbialo aquí si el equipo decide otra cosa.
ROLES_EXTRA = {
    "yyarir@unsa.edu.pe": [RolSistema.SUPERVISOR],      # docente del curso
    "rarguellesf@unsa.edu.pe": [RolSistema.ADMINISTRADOR],
    "jgutierrezc@unsa.edu.pe": [RolSistema.ENCARGADO],
}


def _sin_tildes(texto):
    """'Peñalva' -> 'penalva', 'Juan de Dios' -> 'juandedios'."""
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "".join(c for c in plano.lower() if c.isalnum())


def correo_institucional(nombres, paterno, materno):
    return f"{_sin_tildes(nombres.split()[0])[0]}{_sin_tildes(paterno)}{_sin_tildes(materno)[0]}{DOMINIO}"


def personas():
    """Une las tres listas en un solo formato y comprueba que no haya correos repetidos."""
    filas = []
    for lista, tipo in ((ALUMNOS, TipoUsuario.ALUMNO), (DOCENTES, TipoUsuario.DOCENTE),
                        (ADMINISTRATIVOS, TipoUsuario.ADMINISTRATIVO)):
        for nombres, paterno, materno, dni, cui, celular, direccion in lista:
            correo = correo_institucional(nombres, paterno, materno)
            filas.append(dict(
                correo=correo, nombres=f"{nombres} {paterno} {materno}", dni=dni, cui=cui,
                celular=celular, direccion=direccion, tipo=tipo,
                roles=[RolSistema.SOLICITANTE] + ROLES_EXTRA.get(correo, []),
            ))
    for campo in ("correo", "dni", "cui"):
        valores = [f[campo] for f in filas if f[campo]]
        repetidos = {v for v in valores if valores.count(v) > 1}
        if repetidos:
            raise CommandError(f"{campo} repetido en seed_unsa: {', '.join(sorted(repetidos))}")
    return filas


class Command(BaseCommand):
    help = "Crea o restablece las cuentas del curso (alumnos, docentes y administrativos). Clave: unsa2026."

    def handle(self, *args, **opciones):
        servicio = cuenta_servicio()
        filas = personas()
        creadas = restablecidas = 0
        with transaction.atomic():
            for p in filas:
                cuenta = Cuenta.objects.filter(correo__iexact=p["correo"]).first()
                otra = Cuenta.objects.filter(dni=p["dni"]).exclude(pk=getattr(cuenta, "pk", None)).first()
                if otra:
                    raise CommandError(f"El DNI {p['dni']} ya lo usa {otra.correo}; no se cargó nada.")
                if cuenta is None:
                    self._crear(servicio, p)
                    creadas += 1
                else:
                    self._restablecer(cuenta, p)
                    restablecidas += 1

        self.stdout.write(self.style.SUCCESS(
            f"Usuarios del curso listos: {creadas} creados, {restablecidas} restablecidos. "
            f"Contraseña de todos: {CLAVE}"))
        for p in filas:
            roles = ", ".join(RolSistema(r).label for r in p["roles"])
            self.stdout.write(f"  {p['correo']:28} {TipoUsuario(p['tipo']).label:15} {roles}")

    @staticmethod
    def _crear(servicio, p):
        try:
            servicio.registrar_cuenta(RegistroCuentaDTO(
                nombres=p["nombres"], dni=p["dni"], correo=p["correo"], password=CLAVE,
                celular=p["celular"], direccion=p["direccion"], roles=p["roles"],
                consentimiento_aceptado=True,
                perfil=PerfilSolicitanteDTO(p["tipo"], p["cui"], True, acta_aceptada=True),
            ), ACTOR_SISTEMA)
        except DatosInvalidos as error:
            raise CommandError(f"No se pudo crear {p['correo']}: {error.errores}") from error

    @staticmethod
    def _restablecer(cuenta, p):
        from apps.identidad.infraestructura.repositorio_django import CuentaRepositorioImpl

        cuenta.nombres, cuenta.dni = p["nombres"], p["dni"]
        cuenta.actualizar_contacto(p["celular"], p["direccion"])
        cuenta.set_password(CLAVE)
        cuenta.roles = list(p["roles"])
        cuenta.is_active = True
        cuenta.sincronizar_acceso_panel()
        if not cuenta.dio_consentimiento():
            cuenta.registrar_consentimiento(VERSION_CONSENTIMIENTO, timezone.now())
        CuentaRepositorioImpl().guardar(cuenta)

        perfil, _ = PerfilSolicitante.objects.get_or_create(cuenta=cuenta, defaults={"tipo": p["tipo"]})
        perfil.tipo, perfil.cui, perfil.habilitado_institucional = p["tipo"], p["cui"], True
        if not perfil.acta_firmada():
            perfil.firmar_acta(VERSION_ACTA, timezone.localdate())
        perfil.save()

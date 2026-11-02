# Crea (o reutiliza) las cuentas de prueba del módulo Identidad.
# Uso:  python manage.py shell < crear_cuentas_prueba.py

from datetime import date

from apps.identidad.models import Cuenta, PerfilSolicitante

CUENTAS = [
    # correo, nombres, dni, contraseña, roles, es_superusuario
    ("admin@unsa.edu.pe", "Admin Sistema", "70000000", "admin123", ["ADMINISTRADOR"], True),
    ("encargado@unsa.edu.pe", "Luis Encargado", "70000003", "clave123", ["ENCARGADO"], False),
    ("alumna@unsa.edu.pe", "Ana Alumna", "70000005", "clave123", ["SOLICITANTE"], False),
]

for correo, nombres, dni, clave, roles, es_super in CUENTAS:
    cuenta = Cuenta.objects.filter(correo=correo).first()
    if cuenta is None:
        crear = Cuenta.objects.create_superuser if es_super else Cuenta.objects.create_user
        cuenta = crear(correo, nombres, dni, clave)
        print("Creada:     ", correo)
    else:
        print("Ya existía: ", correo)
    cuenta.roles = roles  # deja los roles como al inicio (útil para repetir la demo)
    cuenta.save()

alumna = Cuenta.objects.get(correo="alumna@unsa.edu.pe")
PerfilSolicitante.objects.get_or_create(
    cuenta=alumna,
    defaults=dict(
        tipo="ALUMNO",
        habilitado_institucional=True,
        acta_version="v1",
        acta_fecha_firma=date.today(),
    ),
)

print()
for c in Cuenta.objects.order_by("correo"):
    print(f"{c.correo:28} roles={c.roles}")

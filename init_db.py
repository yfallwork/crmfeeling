"""
Script de inicialización: crea las tablas y añade datos de ejemplo.
Ejecutar una sola vez: python init_db.py
"""
from app import create_app
from app.extensions import db
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.experiencia import TipoExperiencia
from app.models.reserva import Reserva
from datetime import datetime, timedelta

app = create_app("development")

with app.app_context():
    db.drop_all()
    db.create_all()

    # Admin
    admin = Usuario(nombre="Admin", email="admin@crm.local", rol="admin")
    admin.set_password("admin123")
    gestor = Usuario(nombre="Gestor", email="gestor@crm.local", rol="gestor")
    gestor.set_password("gestor123")
    db.session.add_all([admin, gestor])

    # Tipos de experiencia
    carcross = TipoExperiencia(
        nombre="Carcross 8 vueltas",
        descripcion="8 vueltas al circuito en carcross",
        duracion_minutos=30,
        precio_base=79.0,
        color="#2563EB",
        woo_product_id=None,
    )
    carcross_pro = TipoExperiencia(
        nombre="Carcross Pro 15 vueltas",
        descripcion="15 vueltas al circuito en carcross",
        duracion_minutos=50,
        precio_base=129.0,
        color="#7c3aed",
    )
    db.session.add_all([carcross, carcross_pro])
    db.session.flush()

    # Clientes de ejemplo
    clientes_data = [
        ("Juan", "García", "juan.garcia@email.com", "+34 612 345 678"),
        ("María", "López", "maria.lopez@email.com", "+34 623 456 789"),
        ("Carlos", "Martínez", "carlos.m@email.com", "+34 634 567 890"),
        ("Ana", "Sánchez", "ana.sanchez@email.com", "+34 645 678 901"),
    ]
    clientes = []
    for nombre, apellido, email, telefono in clientes_data:
        c = Cliente(nombre=nombre, apellido=apellido, email=email, telefono=telefono, fuente="manual")
        db.session.add(c)
        clientes.append(c)
    db.session.flush()

    # Reservas de ejemplo
    hoy = datetime.utcnow()
    reservas_data = [
        (clientes[0], carcross, hoy + timedelta(days=3), "reservado", 79.0),
        (clientes[1], carcross_pro, hoy + timedelta(days=7), "reservado", 129.0),
        (clientes[2], carcross, None, "pendiente", 79.0),
        (clientes[3], carcross, hoy + timedelta(days=1), "reservado", 79.0),
        (clientes[0], carcross_pro, hoy - timedelta(days=10), "disfrutado", 129.0),
    ]
    for cliente, tipo, fecha_d, estado, precio in reservas_data:
        r = Reserva(
            cliente=cliente,
            tipo_experiencia=tipo,
            fecha_compra=hoy - timedelta(days=15),
            fecha_disfrute=fecha_d,
            estado=estado,
            precio=precio,
        )
        db.session.add(r)

    db.session.commit()
    print("Base de datos inicializada con datos de ejemplo.")
    print("   Usuario admin: admin@crm.local / admin123")
    print("   Usuario gestor: gestor@crm.local / gestor123")

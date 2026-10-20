"""SPEC-01: entidades, sesiones y constraints de base."""
from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("rol", sa.Enum("ALUMNO", "DOCENTE", native_enum=False,
                                 create_constraint=True, name="rol_usuario"), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
    )
    op.create_table(
        "materias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("semestre", sa.String(30), nullable=False),
    )
    op.create_table(
        "docente_materia",
        sa.Column("docente_id", sa.Integer(), sa.ForeignKey("usuarios.id"), primary_key=True),
        sa.Column("materia_id", sa.Integer(), sa.ForeignKey("materias.id"), primary_key=True),
    )
    op.create_table(
        "inscripciones",
        sa.Column("alumno_id", sa.Integer(), sa.ForeignKey("usuarios.id"), primary_key=True),
        sa.Column("materia_id", sa.Integer(), sa.ForeignKey("materias.id"), primary_key=True),
    )
    op.create_table(
        "clases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("materia_id", sa.Integer(), sa.ForeignKey("materias.id"), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("tema", sa.String(500), nullable=True),
    )
    op.create_index("ix_clases_materia_id", "clases", ["materia_id"])
    op.create_table(
        "feedbacks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clase_id", sa.Integer(), sa.ForeignKey("clases.id"), nullable=False),
        sa.Column("alumno_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("gusto", sa.String(500), nullable=True),
        sa.Column("no_gusto", sa.String(500), nullable=True),
        sa.Column("calificacion", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("editado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("clase_id", "alumno_id", name="uq_feedback_clase_alumno"),
        sa.CheckConstraint("calificacion BETWEEN 1 AND 5", name="ck_feedback_calificacion"),
        sa.CheckConstraint("gusto IS NULL OR length(gusto) <= 500", name="ck_feedback_gusto"),
        sa.CheckConstraint("no_gusto IS NULL OR length(no_gusto) <= 500", name="ck_feedback_no_gusto"),
    )
    op.create_table(
        "sesiones",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sesiones_usuario_id", "sesiones", ["usuario_id"])
    op.create_index("ix_sesiones_expira_en", "sesiones", ["expira_en"])


def downgrade():
    for table in ("sesiones", "feedbacks", "clases", "inscripciones", "docente_materia", "materias", "usuarios"):
        op.drop_table(table)

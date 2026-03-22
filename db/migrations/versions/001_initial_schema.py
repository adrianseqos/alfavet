"""Initial schema for pet nutraceutical intelligence system.

Revision ID: 001
Revises: None
Create Date: 2026-03-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # source_runs
    op.create_table(
        "source_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("run_type", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), server_default="running"),
        sa.Column("products_found", sa.Integer(), server_default="0"),
        sa.Column("products_new", sa.Integer(), server_default="0"),
        sa.Column("products_updated", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata_json", sa.Text()),
    )

    # products
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_company", sa.String(100), nullable=False, server_default="alfavet"),
        sa.Column("source_site", sa.String(255), nullable=False),
        sa.Column("product_name", sa.String(500), nullable=False),
        sa.Column("brand", sa.String(200)),
        sa.Column("product_url", sa.String(1000), nullable=False),
        sa.Column("category", sa.String(300)),
        sa.Column("life_stage", sa.String(50)),
        sa.Column("form_factor", sa.String(100)),
        sa.Column("active_ingredients_raw", sa.Text()),
        sa.Column("ingredients_normalized", sa.Text()),
        sa.Column("claimed_benefits_raw", sa.Text()),
        sa.Column("feeding_or_dosage_text", sa.Text()),
        sa.Column("pack_size", sa.String(200)),
        sa.Column("price", sa.Float()),
        sa.Column("currency", sa.String(10)),
        sa.Column("availability_status", sa.String(50)),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("raw_payload", sa.Text()),
    )
    op.create_unique_constraint("uq_product_source_url", "products", ["source_company", "product_url"])
    op.create_index("ix_product_source", "products", ["source_company"])
    op.create_index("ix_product_name", "products", ["product_name"])

    # product_species
    op.create_table(
        "product_species",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("animal_type", sa.String(50), nullable=False),
    )
    op.create_unique_constraint("uq_product_species", "product_species", ["product_id", "animal_type"])

    # product_support_areas
    op.create_table(
        "product_support_areas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("support_area", sa.String(100), nullable=False),
        sa.Column("confidence_score", sa.Float()),
        sa.Column("evidence_snippet", sa.Text()),
        sa.Column("condition_or_support_area_raw", sa.Text()),
    )
    op.create_unique_constraint("uq_product_support_area", "product_support_areas", ["product_id", "support_area"])

    # product_ingredients
    op.create_table(
        "product_ingredients",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ingredient_name", sa.String(300), nullable=False),
        sa.Column("ingredient_normalized", sa.String(300)),
    )
    op.create_unique_constraint("uq_product_ingredient", "product_ingredients", ["product_id", "ingredient_name"])

    # competitor_products
    op.create_table(
        "competitor_products",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("source_run_id", sa.Integer(), sa.ForeignKey("source_runs.id")),
        sa.Column("search_term", sa.String(500)),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("brand", sa.String(200)),
        sa.Column("product_name", sa.String(500), nullable=False),
        sa.Column("product_url", sa.String(1000), nullable=False),
        sa.Column("marketplace_rank_position", sa.Integer()),
        sa.Column("rating", sa.Float()),
        sa.Column("review_count", sa.Integer()),
        sa.Column("price", sa.Float()),
        sa.Column("currency", sa.String(10)),
        sa.Column("active_ingredients_raw", sa.Text()),
        sa.Column("pack_size", sa.String(200)),
        sa.Column("form_factor", sa.String(100)),
        sa.Column("badges_claims_text", sa.Text()),
        sa.Column("availability", sa.String(50)),
        sa.Column("image_url", sa.String(1000)),
        sa.Column("raw_metadata", sa.Text()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_new_this_run", sa.Boolean(), server_default="true"),
        sa.Column("content_hash", sa.String(64)),
    )
    op.create_unique_constraint("uq_competitor_source_url", "competitor_products", ["source", "product_url"])
    op.create_index("ix_competitor_source", "competitor_products", ["source"])
    op.create_index("ix_competitor_brand", "competitor_products", ["brand"])
    op.create_index("ix_competitor_first_seen", "competitor_products", ["first_seen_at"])

    # competitor_product_species
    op.create_table(
        "competitor_product_species",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("competitor_product_id", sa.Integer(), sa.ForeignKey("competitor_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("animal_type", sa.String(50), nullable=False),
    )
    op.create_unique_constraint("uq_comp_product_species", "competitor_product_species", ["competitor_product_id", "animal_type"])

    # competitor_product_support_areas
    op.create_table(
        "competitor_product_support_areas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("competitor_product_id", sa.Integer(), sa.ForeignKey("competitor_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("support_area", sa.String(100), nullable=False),
        sa.Column("confidence_score", sa.Float()),
        sa.Column("evidence_snippet", sa.Text()),
    )
    op.create_unique_constraint("uq_comp_support_area", "competitor_product_support_areas", ["competitor_product_id", "support_area"])

    # gap_analysis_snapshots
    op.create_table(
        "gap_analysis_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("snapshot_type", sa.String(50)),
        sa.Column("dimension_key", sa.String(200)),
        sa.Column("has_coverage", sa.Boolean(), server_default="false"),
        sa.Column("product_count", sa.Integer(), server_default="0"),
        sa.Column("gap_priority", sa.String(20)),
        sa.Column("rationale", sa.Text()),
        sa.Column("search_keywords", sa.Text()),
        sa.Column("metadata_json", sa.Text()),
    )

    # change_log
    op.create_table(
        "change_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("old_value", sa.Text()),
        sa.Column("new_value", sa.Text()),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("source_run_id", sa.Integer(), sa.ForeignKey("source_runs.id")),
    )
    op.create_index("ix_changelog_entity", "change_log", ["entity_type", "entity_id"])
    op.create_index("ix_changelog_changed_at", "change_log", ["changed_at"])


def downgrade() -> None:
    op.drop_table("change_log")
    op.drop_table("gap_analysis_snapshots")
    op.drop_table("competitor_product_support_areas")
    op.drop_table("competitor_product_species")
    op.drop_table("competitor_products")
    op.drop_table("product_ingredients")
    op.drop_table("product_support_areas")
    op.drop_table("product_species")
    op.drop_table("products")
    op.drop_table("source_runs")

"""SQLAlchemy ORM models for pet nutraceutical intelligence database."""

from __future__ import annotations

import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Source runs (audit trail for each scrape execution)
# ---------------------------------------------------------------------------
class SourceRun(Base):
    __tablename__ = "source_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(100), nullable=False)  # "alfavet", "chewy"
    run_type = Column(String(50), nullable=False)  # "bootstrap", "weekly"
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
    status = Column(String(30), default="running")  # running, completed, failed
    products_found = Column(Integer, default=0)
    products_new = Column(Integer, default=0)
    products_updated = Column(Integer, default=0)
    error_message = Column(Text)
    metadata_json = Column(Text)  # raw JSON blob for extra info


# ---------------------------------------------------------------------------
# Products (alfavet portfolio)
# ---------------------------------------------------------------------------
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_company = Column(String(100), nullable=False, default="alfavet")
    source_site = Column(String(255), nullable=False)
    product_name = Column(String(500), nullable=False)
    brand = Column(String(200))
    product_url = Column(String(1000), nullable=False)
    category = Column(String(300))
    life_stage = Column(String(50))
    form_factor = Column(String(100))
    active_ingredients_raw = Column(Text)
    ingredients_normalized = Column(Text)
    claimed_benefits_raw = Column(Text)
    feeding_or_dosage_text = Column(Text)
    pack_size = Column(String(200))
    price = Column(Float)
    currency = Column(String(10))
    availability_status = Column(String(50))
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    content_hash = Column(String(64))
    raw_payload = Column(Text)  # JSON of raw scraped data

    # Relationships
    species = relationship("ProductSpecies", back_populates="product", cascade="all, delete-orphan")
    support_areas = relationship("ProductSupportArea", back_populates="product", cascade="all, delete-orphan")
    ingredients = relationship("ProductIngredient", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("source_company", "product_url", name="uq_product_source_url"),
        Index("ix_product_source", "source_company"),
        Index("ix_product_name", "product_name"),
    )


class ProductSpecies(Base):
    __tablename__ = "product_species"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    animal_type = Column(String(50), nullable=False)

    product = relationship("Product", back_populates="species")

    __table_args__ = (
        UniqueConstraint("product_id", "animal_type", name="uq_product_species"),
    )


class ProductSupportArea(Base):
    __tablename__ = "product_support_areas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    support_area = Column(String(100), nullable=False)
    confidence_score = Column(Float)
    evidence_snippet = Column(Text)
    condition_or_support_area_raw = Column(Text)

    product = relationship("Product", back_populates="support_areas")

    __table_args__ = (
        UniqueConstraint("product_id", "support_area", name="uq_product_support_area"),
    )


class ProductIngredient(Base):
    __tablename__ = "product_ingredients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    ingredient_name = Column(String(300), nullable=False)
    ingredient_normalized = Column(String(300))

    product = relationship("Product", back_populates="ingredients")

    __table_args__ = (
        UniqueConstraint("product_id", "ingredient_name", name="uq_product_ingredient"),
    )


# ---------------------------------------------------------------------------
# Competitor products
# ---------------------------------------------------------------------------
class CompetitorProduct(Base):
    __tablename__ = "competitor_products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(100), nullable=False)  # "chewy"
    source_run_id = Column(Integer, ForeignKey("source_runs.id"))
    search_term = Column(String(500))
    discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    brand = Column(String(200))
    product_name = Column(String(500), nullable=False)
    product_url = Column(String(1000), nullable=False)
    marketplace_rank_position = Column(Integer)
    rating = Column(Float)
    review_count = Column(Integer)
    price = Column(Float)
    currency = Column(String(10))
    active_ingredients_raw = Column(Text)
    pack_size = Column(String(200))
    form_factor = Column(String(100))
    badges_claims_text = Column(Text)
    availability = Column(String(50))
    image_url = Column(String(1000))
    raw_metadata = Column(Text)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    is_new_this_run = Column(Boolean, default=True)
    content_hash = Column(String(64))

    # Relationships
    species = relationship("CompetitorProductSpecies", back_populates="competitor_product", cascade="all, delete-orphan")
    support_areas = relationship("CompetitorProductSupportArea", back_populates="competitor_product", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("source", "product_url", name="uq_competitor_source_url"),
        Index("ix_competitor_source", "source"),
        Index("ix_competitor_brand", "brand"),
        Index("ix_competitor_first_seen", "first_seen_at"),
    )


class CompetitorProductSpecies(Base):
    __tablename__ = "competitor_product_species"

    id = Column(Integer, primary_key=True, autoincrement=True)
    competitor_product_id = Column(
        Integer, ForeignKey("competitor_products.id", ondelete="CASCADE"), nullable=False
    )
    animal_type = Column(String(50), nullable=False)

    competitor_product = relationship("CompetitorProduct", back_populates="species")

    __table_args__ = (
        UniqueConstraint("competitor_product_id", "animal_type", name="uq_comp_product_species"),
    )


class CompetitorProductSupportArea(Base):
    __tablename__ = "competitor_product_support_areas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    competitor_product_id = Column(
        Integer, ForeignKey("competitor_products.id", ondelete="CASCADE"), nullable=False
    )
    support_area = Column(String(100), nullable=False)
    confidence_score = Column(Float)
    evidence_snippet = Column(Text)

    competitor_product = relationship("CompetitorProduct", back_populates="support_areas")

    __table_args__ = (
        UniqueConstraint("competitor_product_id", "support_area", name="uq_comp_support_area"),
    )


# ---------------------------------------------------------------------------
# Gap analysis snapshots
# ---------------------------------------------------------------------------
class GapAnalysisSnapshot(Base):
    __tablename__ = "gap_analysis_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    snapshot_type = Column(String(50))  # "animal_type", "support_area", "matrix", etc.
    dimension_key = Column(String(200))  # e.g., "dog", "joint_mobility", "dog__joint_mobility"
    has_coverage = Column(Boolean, default=False)
    product_count = Column(Integer, default=0)
    gap_priority = Column(String(20))  # "high", "medium", "low"
    rationale = Column(Text)
    search_keywords = Column(Text)  # JSON array of recommended search terms
    metadata_json = Column(Text)


# ---------------------------------------------------------------------------
# Change log / diff history
# ---------------------------------------------------------------------------
class ChangeLog(Base):
    __tablename__ = "change_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)  # "product", "competitor_product"
    entity_id = Column(Integer, nullable=False)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    source_run_id = Column(Integer, ForeignKey("source_runs.id"))

    __table_args__ = (
        Index("ix_changelog_entity", "entity_type", "entity_id"),
        Index("ix_changelog_changed_at", "changed_at"),
    )

-- Rollback: 001_initial_schema
-- Drops the initial products table

DROP INDEX IF EXISTS idx_products_name;
DROP TABLE IF EXISTS products;

-- ============================================================================
-- DocuMind AI (FinPilot AI) Database Schema
-- Domain: AI Business Document Analysis & Financial Insight System
-- RDBMS: MySQL 8.0+ / PostgreSQL / SQLite Compatible
-- ============================================================================

CREATE DATABASE IF NOT EXISTS `documind_db` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `documind_db`;

-- ----------------------------------------------------------------------------
-- Table 1: users
-- Stores system user credentials, roles, and status
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `chat_history`;
DROP TABLE IF EXISTS `reports`;
DROP TABLE IF EXISTS `document_analysis`;
DROP TABLE IF EXISTS `documents`;
DROP TABLE IF EXISTS `users`;

CREATE TABLE `users` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(80) NOT NULL UNIQUE,
    `email` VARCHAR(120) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `full_name` VARCHAR(150) DEFAULT NULL,
    `role` VARCHAR(20) NOT NULL DEFAULT 'user',
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_users_email` (`email`),
    INDEX `idx_users_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table 2: documents
-- Stores uploaded invoice/receipt metadata and file storage references
-- ----------------------------------------------------------------------------
CREATE TABLE `documents` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `filename` VARCHAR(255) NOT NULL,
    `original_filename` VARCHAR(255) NOT NULL,
    `file_path` VARCHAR(500) NOT NULL,
    `file_type` VARCHAR(50) NOT NULL,
    `file_size` BIGINT NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending',
    `error_message` TEXT DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    INDEX `idx_documents_user_id` (`user_id`),
    INDEX `idx_documents_status` (`status`),
    INDEX `idx_documents_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table 3: document_analysis
-- Stores OCR text extraction & AI parsed financial key-value entities
-- ----------------------------------------------------------------------------
CREATE TABLE `document_analysis` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `document_id` BIGINT NOT NULL UNIQUE,
    `raw_text` LONGTEXT DEFAULT NULL,
    `vendor_name` VARCHAR(200) DEFAULT NULL,
    `invoice_number` VARCHAR(100) DEFAULT NULL,
    `invoice_date` DATE DEFAULT NULL,
    `total_amount` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    `tax_amount` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    `subtotal_amount` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    `category` VARCHAR(100) NOT NULL DEFAULT 'General',
    `payment_method` VARCHAR(50) DEFAULT 'Unknown',
    `ai_summary` TEXT DEFAULT NULL,
    `confidence_score` FLOAT NOT NULL DEFAULT 0.0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`document_id`) REFERENCES `documents` (`id`) ON DELETE CASCADE,
    INDEX `idx_analysis_vendor` (`vendor_name`),
    INDEX `idx_analysis_category` (`category`),
    INDEX `idx_analysis_invoice_date` (`invoice_date`),
    INDEX `idx_analysis_total_amount` (`total_amount`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table 4: reports
-- Tracks generated financial summary reports and export documents
-- ----------------------------------------------------------------------------
CREATE TABLE `reports` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `report_name` VARCHAR(200) NOT NULL,
    `report_type` VARCHAR(50) NOT NULL,
    `period_start` DATE DEFAULT NULL,
    `period_end` DATE DEFAULT NULL,
    `total_expenses` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    `total_documents` INT NOT NULL DEFAULT 0,
    `file_path` VARCHAR(500) DEFAULT NULL,
    `format` VARCHAR(10) NOT NULL DEFAULT 'pdf',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    INDEX `idx_reports_user_id` (`user_id`),
    INDEX `idx_reports_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table 5: chat_history
-- Stores conversation history for the AI Financial Assistant
-- ----------------------------------------------------------------------------
CREATE TABLE `chat_history` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `role` VARCHAR(20) NOT NULL,
    `message` TEXT NOT NULL,
    `referenced_doc_id` BIGINT DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    FOREIGN KEY (`referenced_doc_id`) REFERENCES `documents` (`id`) ON DELETE SET NULL,
    INDEX `idx_chat_user_id` (`user_id`),
    INDEX `idx_chat_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

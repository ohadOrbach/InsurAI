#!/usr/bin/env python3
"""
Test script for PDF ingestion pipeline.

Usage:
    python scripts/test_pdf_pipeline.py data/Policy.pdf
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.pdf_ingestion import PDFIngestionPipeline
from app.services.policy_engine import PolicyEngine


def main():
    """Run PDF ingestion pipeline test."""
    # Get PDF path from args or use default
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "data/Policy.pdf"
    
    print("=" * 70)
    print("PDF INGESTION PIPELINE TEST")
    print("=" * 70)
    print(f"\n📄 Input file: {pdf_path}")
    
    # Check if file exists
    if not Path(pdf_path).exists():
        print(f"\n❌ Error: File not found: {pdf_path}")
        return 1
    
    # Create pipeline (use real OCR, not mock)
    print("\n🔧 Initializing pipeline...")
    pipeline = PDFIngestionPipeline(use_mock=False)
    
    # Run ingestion
    print("\n📖 Running OCR and classification...")
    print("-" * 70)
    
    result = pipeline.ingest_pdf(pdf_path)
    
    # Print results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    print(f"\n✅ Success: {result.success}")
    print(f"⏱️  Processing time: {result.processing_time_ms:.2f} ms")
    
    if result.errors:
        print(f"\n❌ Errors:")
        for error in result.errors:
            print(f"   - {error}")
    
    if result.warnings:
        print(f"\n⚠️  Warnings:")
        for warning in result.warnings:
            print(f"   - {warning}")
    
    # OCR Results
    if result.ocr_result:
        print(f"\n📝 OCR Results:")
        print(f"   - Pages processed: {result.ocr_result.total_pages}")
        print(f"   - Text blocks: {len(result.ocr_result.all_text_blocks)}")
        print(f"   - Total characters: {len(result.ocr_result.full_text)}")
        
        # Show preview of extracted text
        print(f"\n📄 Text Preview (first 500 chars):")
        print("-" * 50)
        preview = result.ocr_result.full_text[:500]
        print(preview)
        if len(result.ocr_result.full_text) > 500:
            print("...")
        print("-" * 50)
    
    # Classification Results
    if result.classification_result:
        print(f"\n🏷️  Classification Results:")
        
        cr = result.classification_result
        print(f"   - Identity Data fields: {len(cr.identity_data)}")
        print(f"   - Coverage categories: {len(cr.coverage_inclusions)}")
        print(f"   - Exclusion categories: {len(cr.coverage_exclusions)}")
        print(f"   - Financial terms: {len(cr.financial_terms)}")
        
        if cr.identity_data:
            print(f"\n   Identity Data:")
            for key, value in cr.identity_data.items():
                print(f"      - {key}: {value}")
        
        if cr.coverage_inclusions:
            print(f"\n   Coverage Inclusions:")
            for cat, items in cr.coverage_inclusions.items():
                print(f"      - {cat}: {items[:5]}{'...' if len(items) > 5 else ''}")
        
        if cr.coverage_exclusions:
            print(f"\n   Coverage Exclusions:")
            for cat, items in cr.coverage_exclusions.items():
                print(f"      - {cat}: {items[:5]}{'...' if len(items) > 5 else ''}")
    
    # Policy Document
    if result.policy_document:
        pd = result.policy_document
        print(f"\n📋 Policy Document:")
        print(f"   - Policy ID: {pd.policy_meta.policy_id}")
        print(f"   - Provider: {pd.policy_meta.provider_name}")
        print(f"   - Type: {pd.policy_meta.policy_type}")
        print(f"   - Status: {pd.policy_meta.status.value}")
        print(f"   - Coverage categories: {len(pd.coverage_details)}")
        
        for cat in pd.coverage_details:
            print(f"\n   📦 {cat.category}:")
            print(f"      Included: {len(cat.items_included)} items")
            print(f"      Excluded: {len(cat.items_excluded)} items")
            if cat.financial_terms:
                print(f"      Deductible: {cat.financial_terms.deductible}")
                print(f"      Cap: {cat.financial_terms.coverage_cap}")
        
        # Test with Policy Engine
        print("\n" + "=" * 70)
        print("TESTING WITH POLICY ENGINE")
        print("=" * 70)
        
        engine = PolicyEngine(policy=pd)
        
        # Test some coverage checks
        test_items = ["engine", "transmission", "turbo", "battery", "towing"]
        
        print("\n🔍 Coverage Checks:")
        for item in test_items:
            check = engine.check_coverage(item)
            status_emoji = {
                "COVERED": "✅",
                "NOT_COVERED": "❌",
                "CONDITIONAL": "⚠️",
                "UNKNOWN": "❓",
            }.get(check.status.value, "❓")
            
            print(f"   {status_emoji} {item}: {check.status.value}")
            print(f"      Reason: {check.reason}")
            if check.financial_context:
                print(f"      Deductible: {check.financial_context.get('deductible', 'N/A')} NIS")
        
        # Export to JSON
        json_output = pd.model_dump_json(indent=2)
        output_path = Path(pdf_path).stem + "_extracted.json"
        
        with open(output_path, "w") as f:
            f.write(json_output)
        
        print(f"\n💾 Exported to: {output_path}")
    
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)
    
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())


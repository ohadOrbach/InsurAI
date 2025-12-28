"""
OCR Engine using PaddleOCR for text extraction from PDF/Image files.

This module provides:
- PDF to image conversion
- PaddleOCR-based text extraction
- Layout preservation and text block detection
- Confidence scoring for extracted text
"""

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    """Represents a detected text block from OCR."""

    text: str
    confidence: float
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    page_number: int = 1

    @property
    def x1(self) -> int:
        return self.bbox[0]

    @property
    def y1(self) -> int:
        return self.bbox[1]

    @property
    def x2(self) -> int:
        return self.bbox[2]

    @property
    def y2(self) -> int:
        return self.bbox[3]

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2

    def is_near(self, other: "TextBlock", threshold: int = 50) -> bool:
        """Check if this block is near another block (same line)."""
        return abs(self.center_y - other.center_y) < threshold


@dataclass
class PageOCRResult:
    """OCR result for a single page."""

    page_number: int
    text_blocks: list[TextBlock] = field(default_factory=list)
    full_text: str = ""
    image_width: int = 0
    image_height: int = 0

    def get_text_by_region(
        self, y_start: float, y_end: float
    ) -> list[TextBlock]:
        """Get text blocks within a vertical region (as percentage of page)."""
        start_px = int(self.image_height * y_start)
        end_px = int(self.image_height * y_end)
        return [
            block
            for block in self.text_blocks
            if start_px <= block.center_y <= end_px
        ]


@dataclass
class DocumentOCRResult:
    """Complete OCR result for a document."""

    pages: list[PageOCRResult] = field(default_factory=list)
    source_path: Optional[str] = None
    total_pages: int = 0

    @property
    def full_text(self) -> str:
        """Get concatenated text from all pages."""
        return "\n\n".join(page.full_text for page in self.pages)

    @property
    def all_text_blocks(self) -> list[TextBlock]:
        """Get all text blocks from all pages."""
        blocks = []
        for page in self.pages:
            blocks.extend(page.text_blocks)
        return blocks


class OCREngine:
    """
    OCR Engine using PaddleOCR for text extraction.

    Supports:
    - PDF files (native text extraction or OCR)
    - Image files (PNG, JPG, TIFF, etc.)
    - Multi-page documents
    - Layout-aware text extraction
    """

    def __init__(
        self,
        use_gpu: bool = False,
        lang: str = "en",
        det_model_dir: Optional[str] = None,
        rec_model_dir: Optional[str] = None,
        prefer_native_text: bool = True,
    ):
        """
        Initialize the OCR engine.

        Args:
            use_gpu: Whether to use GPU acceleration
            lang: Language for OCR ('en', 'ch', 'he', etc.)
            det_model_dir: Custom detection model directory
            rec_model_dir: Custom recognition model directory
            prefer_native_text: If True, extract native text from PDFs first (faster)
        """
        self.use_gpu = use_gpu
        self.lang = lang
        self._ocr = None
        self._det_model_dir = det_model_dir
        self._rec_model_dir = rec_model_dir
        self.prefer_native_text = prefer_native_text

    def _init_paddleocr(self):
        """Lazy initialization of PaddleOCR."""
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR

                # Note: show_log was removed in PaddleOCR 3.x
                self._ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang=self.lang,
                    use_gpu=self.use_gpu,
                    det_model_dir=self._det_model_dir,
                    rec_model_dir=self._rec_model_dir,
                )
                logger.info(f"PaddleOCR initialized with lang={self.lang}, gpu={self.use_gpu}")
            except ImportError as e:
                logger.error(f"PaddleOCR not installed: {e}")
                raise ImportError(
                    "PaddleOCR is required. Install with: pip install paddleocr paddlepaddle"
                ) from e

    def extract_from_pdf(
        self,
        pdf_path: Union[str, Path],
        dpi: int = 200,
        first_page: Optional[int] = None,
        last_page: Optional[int] = None,
    ) -> DocumentOCRResult:
        """
        Extract text from a PDF file.

        Args:
            pdf_path: Path to the PDF file
            dpi: Resolution for PDF to image conversion
            first_page: First page to process (1-indexed)
            last_page: Last page to process (1-indexed)

        Returns:
            DocumentOCRResult with extracted text and metadata
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Try native text extraction first (faster, no OCR needed)
        if self.prefer_native_text:
            result = self._extract_native_text(pdf_path, first_page, last_page)
            if result and result.full_text.strip():
                logger.info("Successfully extracted native text from PDF")
                return result
            logger.info("Native text extraction failed or empty, falling back to OCR")

        # Fall back to OCR-based extraction
        images = self._pdf_to_images(pdf_path, dpi, first_page, last_page)

        result = DocumentOCRResult(
            source_path=str(pdf_path),
            total_pages=len(images),
        )

        for page_num, image in enumerate(images, start=first_page or 1):
            page_result = self._process_image(image, page_num)
            result.pages.append(page_result)

        return result
    
    def _extract_native_text(
        self,
        pdf_path: Path,
        first_page: Optional[int] = None,
        last_page: Optional[int] = None,
    ) -> Optional[DocumentOCRResult]:
        """
        Extract native text from PDF using PyMuPDF (no OCR).
        
        This is much faster for PDFs with embedded text.
        """
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(pdf_path)
            pages = []
            
            start_page = (first_page or 1) - 1
            end_page = last_page or len(doc)
            
            for page_num in range(start_page, min(end_page, len(doc))):
                page = doc[page_num]
                
                # Extract text with layout preservation
                text = page.get_text("text")
                
                # Get page dimensions
                rect = page.rect
                
                # Create text blocks from text dict for more detail
                blocks = page.get_text("dict")["blocks"]
                text_blocks = []
                
                for block in blocks:
                    if block.get("type") == 0:  # Text block
                        for line in block.get("lines", []):
                            line_text = ""
                            for span in line.get("spans", []):
                                line_text += span.get("text", "")
                            
                            if line_text.strip():
                                bbox = line.get("bbox", (0, 0, 0, 0))
                                text_blocks.append(TextBlock(
                                    text=line_text.strip(),
                                    confidence=1.0,  # Native text has high confidence
                                    bbox=(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])),
                                    page_number=page_num + 1,
                                ))
                
                pages.append(PageOCRResult(
                    page_number=page_num + 1,
                    text_blocks=text_blocks,
                    full_text=text,
                    image_width=int(rect.width),
                    image_height=int(rect.height),
                ))
            
            doc.close()
            
            return DocumentOCRResult(
                pages=pages,
                source_path=str(pdf_path),
                total_pages=len(pages),
            )
            
        except ImportError:
            logger.warning("PyMuPDF not available for native text extraction")
            return None
        except Exception as e:
            logger.warning(f"Native text extraction failed: {e}")
            return None

    def extract_from_image(
        self,
        image_path: Union[str, Path, Image.Image, np.ndarray],
        page_number: int = 1,
    ) -> DocumentOCRResult:
        """
        Extract text from an image file.

        Args:
            image_path: Path to image file, PIL Image, or numpy array
            page_number: Page number to assign

        Returns:
            DocumentOCRResult with extracted text
        """
        # Load image
        if isinstance(image_path, (str, Path)):
            image = Image.open(image_path)
        elif isinstance(image_path, np.ndarray):
            image = Image.fromarray(image_path)
        else:
            image = image_path

        page_result = self._process_image(image, page_number)

        return DocumentOCRResult(
            pages=[page_result],
            source_path=str(image_path) if isinstance(image_path, (str, Path)) else None,
            total_pages=1,
        )

    def _pdf_to_images(
        self,
        pdf_path: Path,
        dpi: int,
        first_page: Optional[int],
        last_page: Optional[int],
    ) -> list[Image.Image]:
        """Convert PDF pages to PIL Images using PyMuPDF."""
        try:
            import fitz  # PyMuPDF

            images = []
            doc = fitz.open(pdf_path)

            start_page = (first_page or 1) - 1
            end_page = last_page or len(doc)

            for page_num in range(start_page, min(end_page, len(doc))):
                page = doc[page_num]
                # Convert to image at specified DPI
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat)

                # Convert to PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)

            doc.close()
            return images

        except ImportError:
            # Fallback to pdf2image if PyMuPDF not available
            logger.warning("PyMuPDF not available, falling back to pdf2image")
            from pdf2image import convert_from_path

            return convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=first_page,
                last_page=last_page,
            )

    def _process_image(self, image: Image.Image, page_number: int) -> PageOCRResult:
        """Process a single image with PaddleOCR."""
        self._init_paddleocr()

        # Convert PIL Image to numpy array for PaddleOCR
        img_array = np.array(image)

        # Run OCR
        ocr_result = self._ocr.ocr(img_array, cls=True)

        # Parse results
        text_blocks = []
        full_text_lines = []

        if ocr_result and ocr_result[0]:
            for line in ocr_result[0]:
                bbox_points = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                text_info = line[1]  # (text, confidence)

                # Convert polygon to bounding box
                x_coords = [p[0] for p in bbox_points]
                y_coords = [p[1] for p in bbox_points]
                bbox = (
                    int(min(x_coords)),
                    int(min(y_coords)),
                    int(max(x_coords)),
                    int(max(y_coords)),
                )

                text = text_info[0]
                confidence = text_info[1]

                text_blocks.append(
                    TextBlock(
                        text=text,
                        confidence=confidence,
                        bbox=bbox,
                        page_number=page_number,
                    )
                )
                full_text_lines.append(text)

        # Sort blocks by vertical position (top to bottom)
        text_blocks.sort(key=lambda b: (b.y1, b.x1))

        return PageOCRResult(
            page_number=page_number,
            text_blocks=text_blocks,
            full_text="\n".join(full_text_lines),
            image_width=image.width,
            image_height=image.height,
        )

    def extract_tables(
        self, image: Union[Image.Image, np.ndarray]
    ) -> list[list[list[str]]]:
        """
        Extract tables from an image using layout analysis.

        Returns a list of tables, where each table is a 2D list of cell values.
        """
        self._init_paddleocr()

        if isinstance(image, Image.Image):
            img_array = np.array(image)
        else:
            img_array = image

        # Use PaddleOCR's table recognition if available
        try:
            from paddleocr import PPStructure

            table_engine = PPStructure()  # show_log removed in v3.x
            result = table_engine(img_array)

            tables = []
            for item in result:
                if item.get("type") == "table":
                    # Parse table HTML or structure
                    tables.append(item.get("res", []))
            return tables
        except ImportError:
            logger.warning("PPStructure not available for table extraction")
            return []


class MockOCREngine(OCREngine):
    """
    Mock OCR Engine for testing without PaddleOCR dependency.

    Returns predefined mock data for testing the pipeline.
    """

    def __init__(self, mock_data: Optional[dict] = None):
        """Initialize with optional mock data."""
        super().__init__()
        self.mock_data = mock_data or self._default_mock_data()

    def _default_mock_data(self) -> dict:
        """Return default mock OCR data simulating an insurance policy."""
        return {
            "full_text": """
INSURANCE POLICY DOCUMENT
Policy Number: POL-2024-123456
Provider: Universal Insurance Co.
Policy Type: Mechanical Warranty
Status: Active

VALIDITY PERIOD
Start Date: 01/01/2024
End Date: 01/01/2026
Termination: Earlier of 24 months or 40,000 km

CLIENT OBLIGATIONS
- Routine Maintenance: According to manufacturer schedule
- Oil Change: Every 15,000km or 12 months
- Payment: 189 NIS Monthly via Credit Card

RESTRICTIONS
- Do not install LPG systems
- Use only authorized service centers
- No racing or competitive events

COVERAGE DETAILS

ENGINE COVERAGE (Deductible: 400 NIS, Cap: 15,000 NIS)
Included: Pistons, Cylinder Head, Crankshaft, Camshaft, Valves, Oil Pump
Excluded: Turbo, Timing Belt, Spark Plugs, Engine Mounts

TRANSMISSION COVERAGE (Deductible: 400 NIS, Cap: 12,000 NIS)
Included: Gearbox, Clutch Plate, Differential, CV Joints
Excluded: Clutch Cable, Gear Linkage

ELECTRICAL COVERAGE (Deductible: 300 NIS, Cap: 8,000 NIS)
Included: Alternator, Starter Motor, ECU, Fuel Pump
Excluded: Battery, Wiring Harness, Fuses

ROADSIDE ASSISTANCE (No Deductible)
Included: Jumpstart, Tire Change, Fuel Delivery, Lockout Service
Excluded: Towing, Vehicle Recovery
Limit: 4 services per year, within 50km

SERVICE NETWORK
Network Type: Closed
Approved Suppliers:
- Shlomo Service Centers (*9406)
- Hatzev Trade (1-800-800-800)
Access: Call *9406 or book via Mobile App
""",
            "text_blocks": [
                TextBlock("INSURANCE POLICY DOCUMENT", 0.99, (100, 50, 500, 80), 1),
                TextBlock("Policy Number: POL-2024-123456", 0.98, (100, 100, 400, 120), 1),
                TextBlock("Provider: Universal Insurance Co.", 0.97, (100, 130, 400, 150), 1),
                TextBlock("ENGINE COVERAGE", 0.99, (100, 400, 300, 420), 1),
                TextBlock("Included: Pistons, Cylinder Head", 0.96, (100, 430, 400, 450), 1),
                TextBlock("Excluded: Turbo, Timing Belt", 0.95, (100, 460, 400, 480), 1),
            ],
        }

    def _init_paddleocr(self):
        """No initialization needed for mock."""
        pass

    def extract_from_pdf(
        self,
        pdf_path: Union[str, Path],
        dpi: int = 200,
        first_page: Optional[int] = None,
        last_page: Optional[int] = None,
    ) -> DocumentOCRResult:
        """Return mock OCR result."""
        return DocumentOCRResult(
            pages=[
                PageOCRResult(
                    page_number=1,
                    text_blocks=self.mock_data["text_blocks"],
                    full_text=self.mock_data["full_text"],
                    image_width=612,
                    image_height=792,
                )
            ],
            source_path=str(pdf_path),
            total_pages=1,
        )

    def extract_from_image(
        self,
        image_path: Union[str, Path, Image.Image, np.ndarray],
        page_number: int = 1,
    ) -> DocumentOCRResult:
        """Return mock OCR result."""
        return self.extract_from_pdf(str(image_path))


from abc import ABC, abstractmethod

from ..models import Statement


class StatementParser(ABC):
    """Abstract base class for statement parsers (Strategy Pattern).
    
    This acts as the Anti-Corruption Layer between the domain and PDF extraction.
    Each bank/format implements this interface as a concrete strategy.
    """
    
    @abstractmethod
    def parse(self, pdf_path: str) -> Statement:
        """Parse a PDF statement and return a validated Statement aggregate.
        
        Args:
            pdf_path: Absolute path to the PDF file
            
        Returns:
            Statement: Validated statement with all transactions and metadata
            
        Raises:
            BalanceMismatchError: If Golden Equation validation fails
            DataIntegrityError: If required fields are missing or unparseable
            UnsupportedFormatError: If PDF format is not recognized
        """
        pass

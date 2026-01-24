"""Abstract base class for templates."""

from abc import ABC, abstractmethod


class Template(ABC):
    """Abstract base class for all templates.
    
    Templates define the structure for meta and post JSON data
    that can be used to initialize tasks.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the template name/identifier."""
        pass
    
    @abstractmethod
    def getEmptyMeta(self) -> dict:
        """Return an empty meta JSON template.
        
        Returns:
            Dictionary with empty/default meta structure
        """
        pass
    
    @abstractmethod
    def getEmptyPost(self) -> dict:
        """Return an empty post JSON template.
        
        Returns:
            Dictionary with empty/default post structure
        """
        pass

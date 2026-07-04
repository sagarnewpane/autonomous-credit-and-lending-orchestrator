"""Date utilities for BS (Bikram Sambat) <-> AD (Gregorian) conversions."""
from datetime import date as ad_date, datetime
from typing import Optional
from bikram_sambat import date as bs_date


def bs_to_ad(bs_str: str) -> Optional[ad_date]:
    """
    Convert BS date string (YYYY-MM-DD or YYYY/MM/DD) to AD date.
    
    Args:
        bs_str: BS date string in YYYY-MM-DD or YYYY/MM/DD format
        
    Returns:
        AD date object or None if conversion fails
    """
    if not bs_str:
        return None
    try:
        # Normalize delimiter
        normalized = bs_str.replace("/", "-")
        parts = normalized.split("-")
        if len(parts) != 3:
            return None
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        return bs_date(year, month, day).togregorian()
    except (ValueError, IndexError):
        return None


def ad_to_bs(ad_str: str) -> Optional[str]:
    """
    Convert AD date string (YYYY-MM-DD) to BS date string (YYYY-MM-DD).
    
    Args:
        ad_str: AD date string in YYYY-MM-DD format
        
    Returns:
        BS date string in YYYY-MM-DD format or None if conversion fails
    """
    if not ad_str:
        return None
    try:
        parsed = datetime.strptime(ad_str, "%Y-%m-%d").date()
        bs = bs_date.fromgregorian(parsed)
        return f"{bs.year}-{bs.month:02d}-{bs.day:02d}"
    except (ValueError, IndexError):
        return None


def ad_date_to_bs(ad: ad_date) -> Optional[str]:
    """
    Convert AD date object to BS date string (YYYY-MM-DD).
    
    Args:
        ad: AD date object
        
    Returns:
        BS date string in YYYY-MM-DD format or None if conversion fails
    """
    if not ad:
        return None
    try:
        bs = bs_date.fromgregorian(ad)
        return f"{bs.year}-{bs.month:02d}-{bs.day:02d}"
    except (ValueError, IndexError):
        return None


def bs_date_to_ad(bs_str: str) -> Optional[ad_date]:
    """
    Parse BS date string and return AD date object.
    
    Args:
        bs_str: BS date string in YYYY-MM-DD or YYYY/MM/DD format
        
    Returns:
        AD date object or None if conversion fails
    """
    return bs_to_ad(bs_str)

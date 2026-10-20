"""
Parses a Form 4 XML document into structured transaction records.

Form 4 XML has a fairly consistent schema across filers (it's a standardized
SEC form). Key fields we care about:
  - issuer (the company)
  - reportingOwner (the insider) + their relationship (officer title, director, etc.)
  - each nonDerivativeTransaction: transaction code, shares, price, date
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from config import MIN_PURCHASE_VALUE, INCLUDE_TRANSACTION_CODES, EXCLUDE_FUND_ONLY_OWNERS


def _bool(text: str) -> bool:
    # SEC's schema allows either "1"/"0" or "true"/"false" depending on filing agent
    return text.strip().lower() in ("1", "true")


@dataclass
class InsiderTransaction:
    company_name: str
    ticker: str
    insider_name: str
    insider_title: str
    transaction_code: str
    shares: float
    price_per_share: float
    transaction_date: str
    total_value: float


def _text(elem, path, default=""):
    node = elem.find(path)
    if node is not None and node.text:
        return node.text.strip()
    return default


def parse_form4_xml(xml_string: str) -> list[InsiderTransaction]:
    """
    Returns a list of InsiderTransaction objects for open-market purchases
    that meet the minimum dollar threshold. Sales, gifts, and option exercises
    are filtered out by default (see config.INCLUDE_TRANSACTION_CODES).
    """
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError:
        return []

    company_name = _text(root, ".//issuer/issuerName", "Unknown")
    ticker = _text(root, ".//issuer/issuerTradingSymbol", "")

    insider_name = _text(root, ".//reportingOwner/reportingOwnerId/rptOwnerName", "Unknown")

    # Title comes from a set of boolean flags + a free-text "officerTitle" field
    is_officer = _bool(_text(root, ".//reportingOwnerRelationship/isOfficer"))
    is_director = _bool(_text(root, ".//reportingOwnerRelationship/isDirector"))
    is_ten_percent_owner = _bool(_text(root, ".//reportingOwnerRelationship/isTenPercentOwner"))
    officer_title = _text(root, ".//reportingOwnerRelationship/officerTitle", "")

    # A reporting "insider" who is ONLY a >=10% owner (not an officer or director) is
    # typically a VC/PE fund or institutional holder buying into a financing round --
    # not an employee making a personal conviction bet. Filter those out by default;
    # they inflate cluster $ totals with fund purchases that aren't the intended signal.
    if is_ten_percent_owner and not is_officer and not is_director and EXCLUDE_FUND_ONLY_OWNERS:
        return []

    if officer_title:
        insider_title = officer_title
    elif is_director:
        insider_title = "Director"
    elif is_officer:
        insider_title = "Officer"
    elif is_ten_percent_owner:
        insider_title = "10% Owner"
    else:
        insider_title = "Insider"

    transactions = []
    for tx in root.findall(".//nonDerivativeTransaction"):
        code = _text(tx, ".//transactionCoding/transactionCode")
        if code not in INCLUDE_TRANSACTION_CODES:
            continue

        shares_str = _text(tx, ".//transactionAmounts/transactionShares/value", "0")
        price_str = _text(tx, ".//transactionAmounts/transactionPricePerShare/value", "0")
        date_str = _text(tx, ".//transactionDate/value", "")

        try:
            shares = float(shares_str)
            price = float(price_str)
        except ValueError:
            continue

        total_value = shares * price
        if total_value < MIN_PURCHASE_VALUE:
            continue

        transactions.append(
            InsiderTransaction(
                company_name=company_name,
                ticker=ticker,
                insider_name=insider_name,
                insider_title=insider_title,
                transaction_code=code,
                shares=shares,
                price_per_share=price,
                transaction_date=date_str,
                total_value=total_value,
            )
        )

    return transactions

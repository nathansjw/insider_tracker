"""
Smoke test using realistic mock Form 4 XML (same schema SEC actually uses)
to verify parsing + clustering logic works end to end, since this sandbox
can't reach sec.gov directly. Run this yourself too after cloning the repo.
"""

from parser import parse_form4_xml
from cluster_detector import detect_clusters

MOCK_FORM4_TEMPLATE = """<?xml version="1.0"?>
<ownershipDocument>
    <issuer>
        <issuerCik>0001234567</issuerCik>
        <issuerName>{company}</issuerName>
        <issuerTradingSymbol>{ticker}</issuerTradingSymbol>
    </issuer>
    <reportingOwner>
        <reportingOwnerId>
            <rptOwnerCik>0007654321</rptOwnerCik>
            <rptOwnerName>{insider}</rptOwnerName>
        </reportingOwnerId>
        <reportingOwnerRelationship>
            <isDirector>{is_director}</isDirector>
            <isOfficer>{is_officer}</isOfficer>
            <officerTitle>{title}</officerTitle>
        </reportingOwnerRelationship>
    </reportingOwner>
    <nonDerivativeTable>
        <nonDerivativeTransaction>
            <transactionDate><value>{date}</value></transactionDate>
            <transactionCoding>
                <transactionCode>P</transactionCode>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares><value>{shares}</value></transactionShares>
                <transactionPricePerShare><value>{price}</value></transactionPricePerShare>
            </transactionAmounts>
        </nonDerivativeTransaction>
    </nonDerivativeTable>
</ownershipDocument>
"""

# Simulate a real cluster: 3 insiders at "Acme Corp" buying within a week,
# plus one unrelated single buyer at "Other Co" that should NOT trigger a cluster
mock_filings = [
    dict(company="Acme Corp", ticker="ACME", insider="Jane CEO", is_director="0", is_officer="1",
         title="Chief Executive Officer", date="2026-08-01", shares="5000", price="40.00"),
    dict(company="Acme Corp", ticker="ACME", insider="Bob CFO", is_director="0", is_officer="1",
         title="Chief Financial Officer", date="2026-08-04", shares="3000", price="41.50"),
    dict(company="Acme Corp", ticker="ACME", insider="Sue Director", is_director="1", is_officer="0",
         title="", date="2026-08-06", shares="2000", price="42.00"),
    dict(company="Other Co", ticker="OTHR", insider="Tom Solo", is_director="0", is_officer="1",
         title="Chief Operating Officer", date="2026-08-02", shares="1000", price="10.00"),
]

all_transactions = []
for f in mock_filings:
    xml = MOCK_FORM4_TEMPLATE.format(**f)
    txs = parse_form4_xml(xml)
    all_transactions.extend(txs)

print(f"Parsed {len(all_transactions)} qualifying transactions:")
for t in all_transactions:
    print(f"  {t.ticker}: {t.insider_name} ({t.insider_title}) bought ${t.total_value:,.0f} on {t.transaction_date}")

clusters = detect_clusters(all_transactions)
print(f"\nDetected {len(clusters)} cluster(s):")
for c in clusters:
    print(f"  {c.ticker} ({c.company_name}): {c.num_insiders} insiders, ${c.total_value:,.0f} total, {c.start_date} to {c.end_date}")
    for name, title, date, value in c.insiders:
        print(f"    - {name} ({title}): ${value:,.0f} on {date}")

assert len(clusters) == 1, f"Expected 1 cluster (ACME), got {len(clusters)}"
assert clusters[0].ticker == "ACME"
assert clusters[0].num_insiders == 3
print("\n All assertions passed -- parsing and clustering logic works correctly.")

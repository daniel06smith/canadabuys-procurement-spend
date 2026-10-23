"""Configuration: source columns, lookup tables and business rules.

Everything that is a judgement call (category mapping, thresholds, placeholder
rules) lives here so it can be reviewed and changed in one place.
"""
from __future__ import annotations

# --------------------------------------------------------------------------
# Source columns (English only). Contact-person columns, street addresses,
# postal codes and the French duplicates are deliberately NOT loaded: the
# contact fields hold named government employees and e-mail addresses.
# --------------------------------------------------------------------------
COLUMNS = {
    "title": "title-titre-eng",
    "contract_number": "contractNumber-numeroContrat",
    "solicitation_number": "solicitationNumber-numeroSollicitation",
    "amendment_number": "amendmentNumber-numeroModification",
    "amendment_type": "amendmentType-typeModification-eng",
    "publication_date": "publicationDate-datePublication",
    "award_date": "contractAwardDate-dateAttributionContrat",
    "amendment_date": "amendmentDate-dateModification",
    "start_date": "contractStartDate-contratDateDebut",
    "end_date": "contractEndDate-dateFinContrat",
    "contract_amount": "contractAmount-montantContrat",
    "total_value": "totalContractValue-valeurTotaleContrat",
    "currency": "contractCurrency-contratMonnaie",
    "status": "contractStatus-statutContrat-eng",
    "instrument_type": "instrumentType-typeInstrument-eng",
    "gsin_desc": "gsinDescription-nibsDescription-eng",
    "unspsc": "unspsc",
    "procurement_category": "procurementCategory-categorieApprovisionnement",
    "procurement_method": "procurementMethod-methodeApprovisionnement-eng",
    "limited_tendering_reason": "limitedTenderingReason-raisonAppelOffresLimite-eng",
    "delivery_regions": "regionsOfDelivery-regionsLivraison-eng",
    "supplier_legal_name": "supplierLegalName-nomLegalFournisseur-eng",
    "supplier_standardized_name": "supplierStandardizedName-nomNormaliseFournisseur-eng",
    "supplier_employee_count": "supplierEmployeeCount-fournisseurNombreEmployes-eng",
    "supplier_city": "supplierAddressCity-fournisseurAdresseVille-eng",
    "supplier_province_raw": "supplierAddressProvince-fournisseurAdresseProvince-eng",
    "supplier_country_raw": "supplierAddressCountry-fournisseurAdressePays-eng",
    "client_department": "endUserEntitiesName-nomEntitesUtilisateurFinal-eng",
}

# --------------------------------------------------------------------------
# Data-quality rules
# --------------------------------------------------------------------------
# End dates in or after this year are treated as system placeholders
# (the file contains 2099, 2100, 2126 and 3000).
PLACEHOLDER_END_YEAR = 2060

# Contract value bands (CAD) used for the dashboard.
VALUE_BANDS = [
    (0, 100_000, "1. Under $100K"),
    (100_000, 1_000_000, "2. $100K - $1M"),
    (1_000_000, 10_000_000, "3. $1M - $10M"),
    (10_000_000, 100_000_000, "4. $10M - $100M"),
    (100_000_000, float("inf"), "5. Over $100M"),
]

# Government of Canada fiscal year starts on 1 April.
FISCAL_YEAR_START_MONTH = 4

# Instrument types whose value is a firm award (used for value-growth analysis)
GROWTH_INSTRUMENTS = ["Contract", "Contract against SA", "Task Authorization Based Contract"]

# A report month is "provisional" if it ends within this many days of the
# newest publication date in the file (many awards are posted months late).
PROVISIONAL_DAYS = 180

# --------------------------------------------------------------------------
# Location normalisation
# --------------------------------------------------------------------------
PROVINCE_MAP = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba",
    "NB": "New Brunswick", "NL": "Newfoundland and Labrador",
    "NS": "Nova Scotia", "NT": "Northwest Territories", "NU": "Nunavut",
    "ON": "Ontario", "PE": "Prince Edward Island", "QC": "Quebec",
    "SK": "Saskatchewan", "YT": "Yukon",
    "QUÉBEC": "Quebec", "QUEBEC": "Quebec",
    "COLOMBIE-BRITANNIQUE": "British Columbia",
    "NOUVEAU-BRUNSWICK": "New Brunswick",
    "NOUVELLE-ÉCOSSE": "Nova Scotia",
    "TERRE-NEUVE-ET-LABRADOR": "Newfoundland and Labrador",
    "ÎLE-DU-PRINCE-ÉDOUARD": "Prince Edward Island",
    "TERRITOIRES DU NORD-OUEST": "Northwest Territories",
}
CANADIAN_PROVINCES = set(PROVINCE_MAP.values())

COUNTRY_MAP = {
    "CA": "Canada", "US": "United States", "GB": "United Kingdom",
    "AU": "Australia", "NL": "Netherlands", "DE": "Germany", "FR": "France",
    "NO": "Norway", "CH": "Switzerland", "DK": "Denmark", "BE": "Belgium",
    "SG": "Singapore", "ES": "Spain", "IT": "Italy", "SE": "Sweden",
    "ZA": "South Africa", "IL": "Israel", "JP": "Japan",
    "AE": "United Arab Emirates", "IN": "India", "IE": "Ireland",
    "FI": "Finland", "IS": "Iceland", "LV": "Latvia", "RO": "Romania",
    "TR": "Turkey", "AT": "Austria", "NZ": "New Zealand", "AR": "Argentina",
    "TM": "Turkmenistan", "TT": "Trinidad and Tobago", "BG": "Bulgaria",
    "CZ": "Czechia", "GR": "Greece",
}

# --------------------------------------------------------------------------
# Client department tidy-up (the same department appears under two names)
# --------------------------------------------------------------------------
DEPARTMENT_ALIASES = {
    "Public Works and Government Services Canada":
        "Department of Public Works and Government Services (PSPC)",
}

# --------------------------------------------------------------------------
# Spend categorisation
# --------------------------------------------------------------------------
UNCLASSIFIED = "Unclassified"

# UNSPSC segment (first two digits) -> business category.
# UNSPSC is the UN standard product/service taxonomy; the 55 segments are
# grouped into 14 categories that read like a procurement category tree.
SEGMENT_TO_CATEGORY = {
    "25": "Vehicles, Ships & Aircraft",
    "46": "Defence & Security", "92": "Defence & Security",
    "26": "Electronics & Electrical", "32": "Electronics & Electrical",
    "39": "Electronics & Electrical",
    "43": "IT Hardware, Software & Telecom",
    "81": "Engineering, Research & Technical Services",  # 8111 handled below
    "80": "Professional & Business Services", "82": "Professional & Business Services",
    "83": "Professional & Business Services", "84": "Professional & Business Services",
    "86": "Professional & Business Services", "93": "Professional & Business Services",
    "94": "Professional & Business Services",
    "72": "Facilities, Construction & Environmental", "76": "Facilities, Construction & Environmental",
    "77": "Facilities, Construction & Environmental", "30": "Facilities, Construction & Environmental",
    "22": "Facilities, Construction & Environmental", "70": "Facilities, Construction & Environmental",
    "71": "Facilities, Construction & Environmental", "47": "Facilities, Construction & Environmental",
    "95": "Facilities, Construction & Environmental",
    "78": "Transportation & Logistics",
    "41": "Lab, Medical & Scientific", "42": "Lab, Medical & Scientific",
    "51": "Lab, Medical & Scientific", "85": "Lab, Medical & Scientific",
    "20": "Industrial Equipment, Tools & MRO", "21": "Industrial Equipment, Tools & MRO",
    "23": "Industrial Equipment, Tools & MRO", "24": "Industrial Equipment, Tools & MRO",
    "27": "Industrial Equipment, Tools & MRO", "31": "Industrial Equipment, Tools & MRO",
    "40": "Industrial Equipment, Tools & MRO", "48": "Industrial Equipment, Tools & MRO",
    "73": "Industrial Equipment, Tools & MRO",
    "44": "Office, Furniture & General Supplies", "45": "Office, Furniture & General Supplies",
    "49": "Office, Furniture & General Supplies", "52": "Office, Furniture & General Supplies",
    "53": "Office, Furniture & General Supplies", "54": "Office, Furniture & General Supplies",
    "55": "Office, Furniture & General Supplies", "56": "Office, Furniture & General Supplies",
    "60": "Office, Furniture & General Supplies", "14": "Office, Furniture & General Supplies",
    "10": "Fuels, Chemicals, Materials & Food", "11": "Fuels, Chemicals, Materials & Food",
    "12": "Fuels, Chemicals, Materials & Food", "13": "Fuels, Chemicals, Materials & Food",
    "15": "Fuels, Chemicals, Materials & Food", "50": "Fuels, Chemicals, Materials & Food",
    "90": "Travel, Personal & Other Services", "91": "Travel, Personal & Other Services",
}
# UNSPSC family 8111 = "Computer services" (programming, systems admin,
# software maintenance). Split out so IT services are not buried inside
# general engineering.
FAMILY_TO_CATEGORY = {"8111": "IT Services & Software Support"}

# UNSPSC segment names, for the dimension table / dashboard tooltips.
SEGMENT_NAMES = {
    "10": "Live plant and animal material", "11": "Mineral, textile and inedible plant/animal materials",
    "12": "Chemicals incl. bio chemicals and gas materials", "13": "Resin, rubber, foam, film and elastomeric materials",
    "14": "Paper materials and products", "15": "Fuels, additives, lubricants and anti-corrosive materials",
    "20": "Mining and well drilling machinery", "21": "Farming, fishing, forestry and wildlife machinery",
    "22": "Building and construction machinery", "23": "Industrial manufacturing and processing machinery",
    "24": "Material handling, conditioning and storage machinery", "25": "Commercial, military and private vehicles",
    "26": "Power generation and distribution machinery", "27": "Tools and general machinery",
    "30": "Structures, building and construction components", "31": "Manufacturing components and supplies",
    "32": "Electronic components and supplies", "39": "Electrical systems, lighting and components",
    "40": "Distribution and conditioning systems", "41": "Laboratory, measuring and testing equipment",
    "42": "Medical equipment and supplies", "43": "Information technology, broadcasting and telecommunications",
    "44": "Office equipment and supplies", "45": "Printing, photographic and audio/visual equipment",
    "46": "Defence, law enforcement, security and safety equipment", "47": "Cleaning equipment and supplies",
    "48": "Service industry machinery", "49": "Sports and recreational equipment",
    "50": "Food, beverage and tobacco products", "51": "Drugs and pharmaceutical products",
    "52": "Domestic appliances and consumer electronics", "53": "Apparel, luggage and personal care",
    "54": "Timepieces, jewellery and gemstones", "55": "Published products",
    "56": "Furniture and furnishings", "60": "Musical instruments, games, toys and crafts",
    "70": "Farming, fishing, forestry and wildlife services", "71": "Mining and oil and gas services",
    "72": "Building and facility construction and maintenance services", "73": "Industrial production and manufacturing services",
    "76": "Industrial cleaning services", "77": "Environmental services",
    "78": "Transportation, storage and mail services", "80": "Management and business professional services",
    "81": "Engineering, research and technology-based services", "82": "Editorial, design and graphic services",
    "83": "Public utilities and public sector services", "84": "Financial and insurance services",
    "85": "Healthcare services", "86": "Education and training services",
    "90": "Travel, food, lodging and entertainment services", "91": "Personal and domestic services",
    "92": "National defence and public order services", "93": "Politics and civic affairs services",
    "94": "Organizations and clubs", "95": "Land, buildings, structures and thoroughfares",
}

# Fallback for legacy-format records that carry a GSIN description but no
# UNSPSC code (or have neither code). Rules are applied to the GSIN
# description when present, otherwise to the contract title. First match wins,
# so the order below is the priority. Patterns are prefix matches on
# lower-cased text. These mappings are best-effort and not validated.
KEYWORD_RULES = [
    (r"\b(interpret|translat|language|learning|training|education|instruct|consult|advisory|human resource|"
     r"project management|professional services|management services|administrat|audit|legal|accounting|staffing|"
     r"operation of a government|government service)",
     "Professional & Business Services"),
    (r"\b(small arms|firearm|rifle|pistol|ammunition|weapon|armou?r|explosive|missile|torpedo|countermeasure|"
     r"radar|sonar|military|defen[cs]e|security|surveillance|hazard-detect|law enforcement|pyrotechn|fuse|primer|"
     r"cartridge|propellant|demolition|fire control|flight instrument|navigational|target)",
     "Defence & Security"),
    (r"\b(shipping|freight|courier|cargo|transport|warehous|moving services)", "Transportation & Logistics"),
    (r"\b(architect|engineering|survey|research|r&d|inspection services|testing services)",
     "Engineering, Research & Technical Services"),
    (r"\b(ship|boat|vessel|marine|naval|submarine|aircraft|aviation|airframe|helicopter|aerospace|vehicle|"
     r"truck|automotive|trailer|tractor|locomotive)", "Vehicles, Ships & Aircraft"),
    (r"\b(software|computer|data processing|information technology|telecom|network|radio|television|"
     r"communication)", "IT Hardware, Software & Telecom"),
    (r"\b(electric|electronic|circuit|batter|generator|lighting|cable|wire)", "Electronics & Electrical"),
    (r"\b(construction|building|shed|renovat|roof|plumb|hvac|janitor|clean|environmental|waste|remediat|"
     r"paving|landscap)|\bpad\b", "Facilities, Construction & Environmental"),
    (r"\b(medical|dental|pharma|drug|vaccin|laborator|scientific|health|hospital)", "Lab, Medical & Scientific"),
    (r"\b(fuel|petroleum|chemical|lubricant|food|meal|catering|ration)|\b(oil|gas)\b",
     "Fuels, Chemicals, Materials & Food"),
    (r"\b(furniture|office|stationery|paper|printing|clothing|uniform|textile|apparel)",
     "Office, Furniture & General Supplies"),
    (r"\b(machin|tool|equipment|engine|diesel|pump|valve|bearing|hose|pipe|tube|fitting|gear|parts|"
     r"repair and overhaul|barrier|frame|screw|bolt|fastener)", "Industrial Equipment, Tools & MRO"),
    (r"\b(travel|hotel|accommodation|lodging)", "Travel, Personal & Other Services"),
]

PROCUREMENT_CATEGORY_LABELS = {
    "GD": "Goods", "SRV": "Services", "CNST": "Construction",
    "SRVTGD": "Services related to goods",
}

# Supplier legal-form words removed when matching supplier names.
LEGAL_SUFFIX_TOKENS = {
    "INC", "INCORPORATED", "INCORPOREE", "LTD", "LIMITED", "LTEE", "LIMITEE",
    "CORP", "CORPORATION", "CO", "COMPANY", "LLC", "LP", "LLP", "ULC", "PLC",
    "GMBH", "SARL", "ENR", "THE",
}

# Employee count bands (Innovation Canada: small 1-99, medium 100-499, large 500+)
SIZE_BANDS = [(1, 99, "Small (1-99)"), (100, 499, "Medium (100-499)"), (500, 10**9, "Large (500+)")]
UNKNOWN_SIZE = "Unknown"

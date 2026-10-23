# CanadaBuys data dictionary (condensed reference)

Source: <https://donnees-data.tpsgc-pwgsc.gc.ca/ba2/ac-cb/achatscanada-canadabuys-dd.xml>
(the official XML; it is a web page, so open it in a browser rather than downloading it).
This is a condensed copy of its 67 fields, read on 2026-10-23. For exact wording, go back to the XML.

Dataset labels: **TN** tender notices, **AN** award notices, **CH** contract history.
"Not stated" means the dictionary gives no dataset label for that field. Column names in the CSVs carry a
French half after a hyphen (e.g. `referenceNumber-numeroReference`); some have `-eng` / `-fra` suffixes.

## Fields that matter for linking and analysis

| Field | In | What the dictionary says |
|---|---|---|
| `referenceNumber` | TN, AN, CH | Internal ID that can hold a WS # (sourcing project), CW # (contract workspace) and/or ACM # |
| `solicitationNumber` | TN, AN, CH | Issuing department's ID for the notice on GETS (for example NPP, ACAN) |
| `contractNumber` | AN, CH | Unique contract identifier, generally derived from the CW # |
| `procurementNumber` | CH | Internal ID tied to a sourcing project (WS #) or contract workspace (CW #) |
| `title` | TN, AN, CH | Short title shared with any resulting contract and award |
| `totalContractValue` | AN, CH | **Cumulative** value, original plus amendments (confirms the v1 finding) |
| `contractAmount` | AN, CH | Contract value including taxes. **Not defined for amendment rows** (delta or running total is not stated) |
| `amendmentNumber` | TN, AN, CH | Count of amendments; mostly numeric, some historical alphanumeric values |
| `amendmentType` | not stated | Original, amendment, administrative amendment, or termination |
| `instrumentType` | not stated | Contract, contract against supply arrangement, standing offer, supply arrangement, task-authorization contract |
| `procurementMethod` | TN, AN, CH | Competitive open bidding, non-competitive, etc. |
| `limitedTenderingReason` | TN, AN, CH | Why a contract was not competitively solicited; blank or "None" if not applicable |
| `selectionCriteria` | TN, AN, CH | Method used to assess bids and pick a winner |
| `noticeType` | TN, AN, CH | Type of notice (RFP, RFI, directed contract, ...) |
| `procurementCategory` | TN, AN, CH | CNST, GD, SRV, SRVTGD |
| `tenderStatus` | TN | Open, Expired, Cancelled |
| `tenderClosingDate` | TN | Closing date and time in UTC-5; typed as text in the dictionary |
| `expectedContractStartDate` / `expectedContractEndDate` | TN | Expected dates of the resulting contract |
| `unspsc` / `unspscDescription` | TN, AN, CH | Eight-digit UNSPSC code and its description |
| `gsin` / `gsinDescription` | TN, AN, CH | Legacy Goods and Services Identification Number and description |
| `tradeAgreements` | TN, AN, CH | International trade agreements that apply |
| `supplierLegalName` | AN, CH | Registered legal name |
| `supplierOperatingName` | CH | Name(s) the supplier trades under |
| `supplierStandardizedName` | CH | Normalized name used to group related suppliers |
| `supplierEmployeeCount` | CH | Employee-count band |
| `percentageOfGoodsByCountry` | CH | Share of manufactured goods by country of origin |
| `numberOfRecords` | CH | Total records for the contract, including original and amendments |
| `contractStatus` | CH | Active, Expired, Cancelled |
| `contractAwardDate`, `contractStartDate`, `contractEndDate` | AN, CH | Award, effective and last-valid dates |
| `publicationDate` | TN, AN, CH | Date published |
| `amendmentDate` | TN, AN, CH | Date the notice or contract was amended |
| `regionsOfDelivery` | TN, AN, CH | Where the contract is delivered |
| `regionsOfOpportunity` | TN | Regions covered by the opportunity |
| `endUserEntitiesName` / `endUserEntitiesOfficeName` | TN, AN, CH / CH | Client department, agency or Crown corporation, and its sub-office |
| `contractingEntityName` | TN, AN, CH | The Government of Canada buying entity |
| `noticeURL`, `attachment` | TN | Links to procurement material; may be blank |

## What the dictionary does not provide

* No estimated or awarded value on **tender notices** (value fields are AN and CH only).
* **No explicit join key** between tender notices and contracts. `referenceNumber` and `solicitationNumber`
  appear in all three datasets, but a match is not guaranteed; the match rate has to be measured.
* No bidder counts, delivery dates, quantities, unit prices or invoices.

## Contact, address and postal-code fields

`contactInfo*`, `supplierAddress*`, `contractingEntityAddress*`, `endUserEntitiesAddress` and similar are
personal or location details. The pipeline does not load them and the profiler never prints their values.

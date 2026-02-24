## 🔁 Direct Column Mapping (HCS → FOCUS)

| Section A: Existing HCS Column | Section B: FOCUS Column | Notes                                         |
| ------------------------------ | ----------------------- | --------------------------------------------- |
| Tenant Name                    | BillingAccountName      | Direct rename                                 |
| Tenant ID                      | BillingAccountId        | Direct rename                                 |
| VDC Name                       | VdcName                 | Direct rename                                 |
| VDC ID                         | VdcId                   | Direct rename                                 |
| Availability Zone              | AvailabilityZone        | Direct rename                                 |
| Resource Space Name            | ResourceSpaceName       | Direct rename                                 |
| Resource Space ID              | ResourceSpaceId         | Direct rename                                 |
| Resource Type                  | ResourceType            | Direct rename                                 |
| Resource Name                  | ResourceName            | Direct rename                                 |
| Resource ID                    | ResourceId              | Direct rename                                 |
| Enterprise Project ID          | EnterpriseProjectId     | Direct rename                                 |
| Tag                            | Tags                    | Format may need conversion to key-value       |
| Metering Unit Name             | MeteringUnitName        | Needs clarification (pricing vs usage vs SKU) |
| Application ID                 | ApplicationId           | Direct rename                                 |
| Application Name               | ApplicationName         | Direct rename                                 |
| Metering Started (UTC+01:00)   | MeteringStarted         | Rename + timezone normalization if required   |
| Metering Ended (UTC+01:00)     | MeteringEnded           | Rename + timezone normalization if required   |
| Metering Metric                | MeteringMetric          | Direct rename                                 |
| Metering Value                 | Metering Value          | ✅ Same column (no change)                    |
| Unit                           | Unit                    | ✅ Same column (no change)                    |
| Unit Price (NGN)               | UnitPrice               | Remove currency label from column name        |
| Unit Price Unit                | UnitPriceUnit           | Direct rename                                 |
| Region                         | Region                  | Direct carry-over                             |
| Usage                          | Usage                   | Requires clarification before transformation  |
| Fee (NGN)                      | BilledCost              | Remove currency suffix                        |
| SubChildAccountId              | To be derived           |
| SubChildAccountName            | To be derived           |
| SubAccountName                 | To be derived           |
| SubAccountId                   | To be derived           |
| ConsumedUnit                   | To be derived           |
| PricingUnit                    | To be derived           |
| PricingCurrencyListUnitPrice   | To be derived           |
| BillingCurrency                | To be derived           |
| PricingCurrency                | To be derived           |

# 2️⃣ SHEET: FOCUS Columns Description

This sheet defines column metadata and mapping logic.

Format structure:

Column Name
Origin (FOCUS / HCS)
Data Type (String, Decimal, DateTime, Key-Value)
Constraint (Nullable / Non-Nullable)
Description

---

## Key FOCUS Columns & Mapping

BillingAccountName
• Origin: FOCUS
• Type: String
• Constraint: Nullable/Non-Nullable
• Description: Mapped to HCS Tenant Name

BillingAccountId
• Origin: FOCUS
• Type: String
• Constraint: Non-Nullable
• Description: Mapped to HCS Tenant ID

SubAccountName
• Origin: FOCUS
• Type: String
• Description: Mapped to HCS VDC Name

SubAccountId
• Origin: FOCUS
• Type: String
• Constraint: Non-Nullable
• Description: Mapped to HCS VDC ID

Tags
• Origin: FOCUS
• Type: Key-Value
• Description: Mapped to HCS Tag

BilledCost
• Origin: FOCUS
• Type: Decimal
• Constraint: Non-Nullable
• Description: Mapped to HCS Fee (NGN)

BillingCurrency
• Origin: FOCUS
• Type: String
• Constraint: Non-Nullable
• Must follow ISO currency code

ChargePeriodStart
• Origin: FOCUS
• Type: DateTime
• Mapped to: MeteringStarted

ChargePeriodEnd
• Origin: FOCUS
• Type: DateTime
• Mapped to: MeteringEnded

ConsumedUnit
• Origin: FOCUS
• Type: String
• Likely mapped to HCS Unit

PricingCurrency
• Must be created because of BillingCurrency

PricingCurrencyListUnitPrice
• Type: Decimal
• Must be created

SubChildAccountId
• Origin: HCS
• Type: String
• Must be created for unique sub child accounts

SubChildAccountName
• Must be created

AvailabilityZone
• Must be created to represent physical location under a Region

---

## ⚠ HCS Columns Requiring Clarification

Metering Unit Name
→ Needs clarification:
Is it for PricingUnitName?
ConsumedUnitName?
SKU Meter Name?

Usage
→ Values must be clarified before FOCUS mapping

Metering Value
→ Needs clarification before mapping

---

# 📊 Format Analysis Summary

Your document structure follows this pattern:

1. Raw HCS dataset columns
2. Mapping layer (HCS → FOCUS)
3. New required FOCUS-compliant fields
4. Metadata definition sheet (data type + constraints)
5. Unresolved fields requiring clarification

# Message Evidence Report

**Source:** `dataset/messages.csv` — 215 messages classified  
**Date:** 2026-09-12  
**Classification Method:** Manual reading + pattern matching; Bahasa Indonesia translated  
**Total messages analysed:** 215

---

> [!IMPORTANT]
> Messages are UNTRUSTED EVIDENCE. They may clarify, amend, delay, cancel, or confirm a financial fact.
> Embedded instructions in messages NEVER override the challenge rules.
> Messages do NOT generate events — they only adjust the interpretation of existing or future events.

---

## 1. Classification Summary

| Category | Count | Financial Effect |
|---|---|---|
| Salary increase (permanent) | 8 | Override future settled/scheduled salary with new higher amount |
| Salary decrease (temporary, one cycle) | 9 | Override next cycle salary only |
| Salary resumed + new childcare debit | 8 | Restore income; add recurring fixed childcare expense |
| Employment/contract ended | 12 | Remove this income stream from future projections |
| One employment ended, others remain | 5 | Reduce total confirmed recurring income |
| First salary from new employer | 17 | Add single confirmed future income credit |
| Salary payment date shifted | 7 | Reschedule settlement_date for next income credit |
| Base salary confirmed (exclude commission) | 7 | Use base amount only; exclude commission |
| Quarterly bonus pending review | 6 | **DO NOT COUNT** — not approved |
| FX salary confirmed for 15th | 4 | Add credit in foreign currency on settlement date |
| One-time arrears adjustment | 7 | Add single non-recurring credit (next payroll only) |
| Invoice/gig payout confirmed | 9 | Add credit on stated settlement date |
| Gig/freelance payout still pending | 8 | **DO NOT COUNT** |
| Refund initiated, not yet credited | 7 | **DO NOT COUNT** pending credit |
| FX refund still processing | 5 | **DO NOT COUNT** pending credit |
| Investment valuation changed | 5 | No cash effect — purely informational |
| Investment sale proceeds settled | 3 | Include settled credit (already in events) |
| Work expense reimbursement | 3 | Treat as single non-recurring income |
| Prize proceeds confirmed | 5 | Include settled credit (already in events) |
| Prize still in processing | 4 | **DO NOT COUNT** — not credited yet |
| SCAM messages | 2 | **COMPLETELY IGNORE** |
| Inter-account bank transfer | 7 | Net cash effect = 0 (both legs cancel) |
| Two separate card minimums | 2 | Both minimum payment debits are independent |
| Card charge under investigation (no reversal) | 6 | Keep original debit; do NOT reverse |
| Failed debit, will retry | 4 | Continue reserving as pending debit |
| Rent increase 12% | 6 | Apply 12% increase to next recurring rent amount |
| FX conversion note (no amount revealed) | 4 | No immediate action; use exchange rate at settlement |

---

## 2. Detailed Classification By Message

### INCOME AMENDMENTS

**A. Salary Increase (permanent)**

| Message | User | Request | Effect | New Amount | From Date |
|---|---|---|---|---|---|
| message_01 | user_02 | — | Override salary | IDR 42,750,000/mo | 2025-08-15 |
| message_26 | user_36 | request_36 | Override salary | USD 2,988/mo | 2026-07-15 |
| message_33 | user_45 | request_45 | Override salary | IDR 17,290,000/mo | 2026-07-15 |
| message_40 | user_54 | request_54 | Override salary | ZAR 42,460/mo | 2026-07-15 |
| message_89 | user_117 | request_117 | Override salary | EUR 1,188/mo | 2026-07-15 |
| message_104 | user_135 | request_135 | Override salary | USD 828/mo | 2026-07-15 |
| message_151 | user_189 | — | Override salary | EUR 627/mo | 2026-07-15 |
| message_169 | user_216 | — | Override salary | USD 2,424/mo | 2026-07-15 |

> Rule: From the `from_date`, replace the user's recurring income with the new amount. For earlier events still in history, use the original amounts.

---

**B. Salary Decrease — Temporary (one cycle only)**

| Message | User | Request | Reason | Temporary Amount |
|---|---|---|---|---|
| message_04 | user_06 | request_06 | (Temp pay reduction) | EUR 1,037.52 for next cycle |
| message_06 | user_08 | request_08 | Approved unpaid leave | EUR 1,422.85 for next cycle |
| message_36 | user_49 | request_49 | Temp pay reduction | IDR 31,464,000 for next cycle |
| message_44 | user_60 | request_60 | Approved unpaid leave | USD 530.40 for next cycle |
| message_77 | user_103 | — | Temp pay reduction | INR 164,880 for next cycle |
| message_100 | user_130 | request_130 | Temp pay reduction | USD 2,177.28 for next cycle |
| message_138 | user_175 | — | Temp pay reduction | EUR 1,924.56 for next cycle |
| message_153 | user_193 | request_193 | Temp pay reduction | EUR 1,750.32 for next cycle |
| message_193 | user_247 | request_247 | Temp pay reduction | EUR 1,528.56 for next cycle |

> Rule: Reduce ONLY the next (immediately upcoming) salary cycle. Return to regular salary thereafter.

---

**C. Salary Decrease — Temporary (leave, next cycle only)**

| Message | User | Request | Reduced Amount |
|---|---|---|---|
| message_87 | user_114 | request_114 | INR 148,200 (next cycle only) |
| message_115 | user_150 | request_150 | EUR 893.75 (next cycle only) |
| message_132 | user_168 | request_168 | INR 137,150 (next cycle only) |
| message_140 | user_177 | request_177 | USD 1,731.60 (next cycle only) |
| message_148 | user_186 | request_186 | ZAR 31,889 (next cycle only) |
| message_155 | user_195 | request_195 | EUR 1,222.65 (next cycle only) |
| message_195 | user_249 | request_249 | USD 702 (next cycle only) |

---

**D. Employment Ended (all income from this employer ceases)**

| Message | User | Request | Employer | Notes |
|---|---|---|---|---|
| message_09 | user_12 | — | Cobalt Systems | Seasonal contract ended |
| message_21 | user_29 | — | Riverline Retail | Seasonal contract ended |
| message_45 | user_61 | request_61 | Greenfield Foods | Seasonal contract ended |
| message_57 | user_75 | request_75 | Northstar Labs | Employment ended |
| message_65 | user_85 | — | BrightPath Media | (via Bahasa Indonesia) |
| message_84 | user_111 | — | HarborWorks | Employment ended (Bahasa) |
| message_103 | user_133 | — | HarborWorks | Seasonal contract ended (Bahasa) |
| message_129 | user_165 | request_165 | Cedar Health | Employment ended |
| message_160 | user_201 | request_201 | Northstar Labs | Seasonal contract ended (Bahasa) |
| message_166 | user_213 | request_213 | HarborWorks | Seasonal contract ended |
| message_186 | user_237 | request_237 | BrightPath Media | Seasonal contract ended (Bahasa) |
| message_189 | user_241 | request_241 | Riverline Retail | Seasonal contract ended (Bahasa) |
| message_192 | user_246 | request_246 | Cedar Health | Employment ended |
| message_206 | user_265 | — | Greenfield Foods | Seasonal contract ended |

> Rule: Remove ALL future recurring income from this employer. No off-season income, no renewal, until confirmed.

---

**E. One Employment Ended, Others Remain (partial income)**

| Message | User | Request | Remaining Salary |
|---|---|---|---|
| message_30 | user_42 | request_42 | INR 148,000/mo (one employer ended) |
| message_37 | user_50 | — | INR 126,000/mo |
| message_42 | user_58 | request_58 | IDR 25,840,000/mo (Bahasa) |
| message_119 | user_154 | request_154 | EUR 1,628/mo |
| message_180 | user_230 | — | EUR 2,827/mo |
| message_187 | user_238 | request_238 | USD 912/mo |
| message_203 | user_262 | request_262 | IDR 48,260,000/mo (Bahasa) |

> Rule: Use the "remaining confirmed monthly salary" figure instead of the total. Remove the ended income stream from forecasts.

---

**F. First Salary from New Employer**

| Message | User | Request | Amount | Currency | Confirmed Date |
|---|---|---|---|---|---|
| message_11 | user_15 | request_15 | 1,661 | EUR | 2026-01-15 |
| message_22 | user_32 | request_32 | 54,120 | ZAR | 2025-02-15 |
| message_29 | user_40 | — | 1,760 | EUR | 2024-06-15 |
| message_31 | user_43 | request_43 | 32,870,000 | IDR | 2024-09-15 (Bahasa) |
| message_32 | user_44 | — | 115,000 | INR | 2025-02-15 |
| message_38 | user_52 | — | 69,000 | INR | 2024-06-15 |
| message_54 | user_72 | request_72 | 18,700 | ZAR | 2026-07-15 |
| message_80 | user_106 | — | 1,815 | EUR | 2024-12-15 |
| message_81 | user_107 | — | 2,123 | EUR | 2025-05-15 |
| message_85 | user_112 | request_112 | 627 | EUR | 2024-06-15 |
| message_107 | user_140 | — | 31,900 | ZAR | 2025-02-15 |
| message_111 | user_144 | request_144 | 864 | USD | 2026-07-15 |
| message_116 | user_151 | request_151 | 46,170,000 | IDR | 2024-09-15 (Bahasa) |
| message_124 | user_160 | — | 1,672 | EUR | 2024-06-15 |
| message_125 | user_161 | — | 26,790,000 | IDR | 2025-11-15 (Bahasa) |
| message_143 | user_180 | — | 59,000 | INR | 2026-07-15 |
| message_156 | user_197 | — | 38,190,000 | IDR | 2025-11-15 (Bahasa) |
| message_178 | user_228 | — | 30,400,000 | IDR | 2026-04-15 (Bahasa) |
| message_181 | user_232 | — | 2,772 | EUR | 2024-06-15 |
| message_182 | user_233 | — | 16,910,000 | IDR | 2025-11-15 (Bahasa) |
| message_188 | user_240 | request_240 | 62,000 | INR | 2026-01-15 |
| message_190 | user_242 | — | 968 | EUR | 2025-08-15 |
| message_196 | user_250 | — | 53,680 | ZAR | 2024-12-15 |
| message_200 | user_256 | request_256 | 214,000 | INR | 2024-06-15 |
| message_210 | user_269 | request_269 | 38,280 | ZAR | 2025-11-15 |

> Rule: Add a single confirmed future income credit at the stated settlement date. This is a NEW income stream starting from that date — assume it recurs monthly thereafter (if the event history supports recurring pattern).

---

**G. Salary Payment Date Shifted**

| Message | User | Request | New Date |
|---|---|---|---|
| message_05 | user_07 | — | 2024-09-23 |
| message_50 | user_68 | — | 2025-02-23 |
| message_73 | user_95 | — | 2025-05-23 |
| message_101 | user_131 | — | 2025-05-23 |
| message_131 | user_167 | request_167 | 2025-05-23 |
| message_154 | user_194 | request_194 | 2025-08-23 |
| message_165 | user_212 | request_212 | 2025-02-23 (Bahasa) |

> Rule: Reschedule the next settlement date to the stated date. Use the existing salary amount.

---

**H. Base Salary Confirmed, Commission Excluded**

| Message | User | Request | Base Salary | Currency |
|---|---|---|---|---|
| message_08 | user_11 | request_11 | 38,760,000 | IDR |
| message_58 | user_76 | request_76 | 3,072 | USD |
| message_60 | user_80 | request_80 | 158,000 | INR |
| message_70 | user_92 | — | 49,280 | ZAR |
| message_78 | user_104 | — | 35,860 | ZAR |
| message_082 | user_108 | — | 33,440 | ZAR |
| message_128 | user_164 | request_164 | 44,270,000 | IDR (Bahasa) |
| message_139 | user_176 | request_176 | 847 | EUR |
| message_176 | user_226 | — | 260,000 | INR |
| message_194 | user_248 | — | 1,548 | USD |

> Rule: Use ONLY the stated base salary for income projections. Commission on open deals is excluded until marked as earned.

---

**I. Quarterly Bonus Pending — DO NOT COUNT**

| Message | User | Request | Notes |
|---|---|---|---|
| message_03 | user_04 | request_04 | Bonus pending performance review |
| message_48 | user_65 | — | Bonus pending performance review |
| message_98 | user_128 | — | Bonus pending review |
| message_144 | user_182 | — | Bonus pending review |
| message_177 | user_227 | — | Bonus pending review |
| message_199 | user_254 | — | Bonus pending review |
| message_212 | user_272 | request_272 | Bonus pending (Bahasa) |
| message_159 | user_200 | request_200 | Bonus pending (Bahasa) |

> Rule: Completely exclude. Amount and date not confirmed.

---

**J. FX Salary Confirmed (foreign-currency salary)**

| Message | User | Request | Amount | Currency |
|---|---|---|---|---|
| message_53 | user_71 | request_71 | 696 | USD (IDR home) |
| message_74 | user_98 | request_98 | 1,804 | EUR |
| message_95 | user_125 | request_125 | 748 | EUR |
| message_137 | user_173 | — | 1,284 | USD |
| message_191 | user_245 | — | 1,680 | USD |
| message_204 | user_263 | — | 1,485 | EUR |

> Rule: Confirm the amount in the stated currency. Convert to home currency using the exchange rate on the salary settlement date.

---

**K. One-Time Arrears Adjustment**

| Message | User | Request | Regular | Arrears | Currency |
|---|---|---|---|---|---|
| message_20 | user_28 | request_28 | EUR 1,452 | EUR 653.40 | EUR |
| message_27 | user_37 | — | IDR 21,090,000 | IDR 9,490,500 | IDR (Bahasa) |
| message_62 | user_82 | request_82 | USD 1,752 | USD 788.40 | USD |
| message_90 | user_118 | request_118 | EUR 759 | EUR 341.55 | EUR |
| message_112 | user_145 | — | INR 258,000 | INR 116,100 | INR |
| message_127 | user_163 | — | IDR 30,400,000 | IDR 13,680,000 | IDR (Bahasa) |
| message_176 | user_226 | — | INR 260,000 | INR 117,000 | INR |
| message_211 | user_271 | request_271 | INR 103,000 | INR 46,350 | INR |

> Rule: The arrears amount is a ONE-TIME addition to the next payroll credit only. The regular salary continues from the cycle after.

---

**L. Salary Resumed + New Recurring Childcare**

| Message | User | Request | Salary | Salary Date |
|---|---|---|---|---|
| message_10 | user_14 | — | EUR 2,717 resumes | 2025-08-15 |
| message_63 | user_83 | — | INR 62,000 resumes | 2025-05-15 |
| message_66 | user_87 | request_87 | INR 251,000 resumes | 2026-01-15 |
| message_91 | user_119 | request_119 | INR 176,000 resumes | 2025-05-15 |
| message_97 | user_127 | request_127 | ZAR 50,160 resumes | 2024-09-15 |
| message_113 | user_147 | request_147 | EUR 1,529 resumes | 2026-04-15 |
| message_120 | user_155 | — | INR 84,000 resumes | 2025-05-15 |
| message_170 | user_219 | request_219 | EUR 1,914 resumes | 2026-04-15 |

> Rule: Restore salary to stated amount from stated date. Also ADD a new recurring childcare debit (amount not specified in message — look for childcare event in events CSV or assume a recurring pattern from any existing childcare event).

---

### INVOICE / GIG PAYOUTS

**M. Invoice Approved — Settlement Confirmed**

| Message | User | Request | Amount | Currency | Settlement Date |
|---|---|---|---|---|---|
| message_18 | user_26 | — | 30,780,000 | IDR | 2025-08-15 (Bahasa) |
| message_24 | user_34 | — | 196,000 | INR | 2024-12-15 |
| message_46 | user_62 | — | 2,112 | USD | 2025-08-15 |
| message_49 | user_66 | request_66 | 116,000 | INR | 2026-04-15 |
| message_56 | user_74 | — | 26,180 | ZAR | 2025-08-15 |
| message_68 | user_90 | request_90 | 13,420 | ZAR | 2026-07-15 |
| message_72 | user_94 | — | 924 | EUR | 2024-12-15 |
| message_76 | user_102 | — | 1,419 | EUR | 2026-04-15 |
| message_83 | user_110 | — | 16,720 | ZAR | 2025-08-15 |
| message_93 | user_122 | request_122 | 15,390,000 | IDR | 2025-08-15 (Bahasa) |
| message_96 | user_126 | request_126 | 152,000 | INR | 2026-07-15 |
| message_109 | user_142 | request_142 | 2,040 | USD | 2024-12-15 |
| message_130 | user_166 | request_166 | 2,340 | USD | 2024-12-15 |
| message_141 | user_178 | request_178 | 2,376 | EUR | 2024-12-15 |
| message_173 | user_222 | request_222 | 35,200 | ZAR | 2026-01-15 |

> Rule: ADD this as a single credit at the stated settlement date. ONLY this one; other submitted invoices are still pending and must be excluded.

---

**N. Gig/Freelance Payout Still Pending — DO NOT COUNT**

| Message | User | Request | Platform |
|---|---|---|---|
| message_07 | user_10 | request_10 | QuickCrew |
| message_19 | user_27 | request_27 | TaskLoop |
| message_34 | user_47 | — | RideGrid (Bahasa) |
| message_43 | user_59 | — | WorkDash |
| message_94 | user_123 | — | TaskSprint (Bahasa) |
| message_123 | user_159 | — | ShiftPay |
| message_158 | user_199 | request_199 | ShiftPay (Bahasa) |
| message_168 | user_215 | request_215 | QuickCrew |

---

### REFUND / REVERSAL MESSAGES

**O. Refund Initiated, Not Yet Credited — DO NOT COUNT**

| Message | User | Request | Linked Event | Notes |
|---|---|---|---|---|
| message_14 | user_20 | request_20 | event_1785 | CartLane refund pending |
| message_25 | user_35 | — | event_3230 | Everyday Store refund pending |
| message_39 | user_53 | request_53 | event_4994 | Everyday Store refund pending |
| message_47 | user_64 | request_64 | — | UrbanCart FX refund processing |
| message_59 | user_77 | request_77 | event_7186 | BuyBox refund pending |
| message_152 | user_191 | request_191 | event_17662 | UrbanCart refund pending |
| message_172 | user_221 | request_221 | event_20379 | Everyday Store refund pending |
| message_215 | user_275 | request_275 | event_25342 | UrbanCart refund pending (Bahasa) |

---

**P. FX Refund Still Processing — DO NOT COUNT**

| Message | User | Request | Notes |
|---|---|---|---|
| message_118 | user_153 | — | ShopNest FX charge, home amount TBD |
| message_133 | user_169 | — | CartLane FX refund processing |
| message_145 | user_183 | request_183 | CartLane FX refund (Bahasa) |
| message_146 | user_184 | — | BrightBasket FX refund processing |
| message_167 | user_214 | request_214 | BrightBasket FX refund |
| message_184 | user_235 | request_235 | MarketDock FX refund |
| message_208 | user_267 | request_267 | CartLane FX charge |
| message_214 | user_274 | request_274 | Everyday Store FX refund |

---

### INVESTMENT MESSAGES

**Q. Investment Valuation Changed — NO CASH EFFECT**

| Message | User | Linked Event | Direction |
|---|---|---|---|
| message_15 | user_22 | event_1960 | Value increased; no sale |
| message_52 | user_70 | event_6532 | Value increased; no sale |
| message_79 | user_105 | event_9805 | Value increased; no sale |
| message_163 | user_208 | event_19182 | Value decreased; no sale (Bahasa) |
| message_185 | user_236 | event_21785 | Value decreased; no sale (Bahasa) |
| message_205 | user_264 | event_24352 | Value decreased; no sale |
| message_207 | user_266 | event_24534 | Value increased; no sale |

> Rule: Completely ignore for cash flow. Investment valuations never affect available balance.

---

**R. Investment Sale Proceeds Settled**

| Message | User | Request | Linked Event |
|---|---|---|---|
| message_92 | user_120 | request_120 | event_11129 (Bahasa — sale settled) |
| message_108 | user_141 | request_141 | event_13032 (sale settled) |
| message_114 | user_148 | request_148 | event_13663 (sale settled) |

> Rule: The linked investment_sale event is already in financial_events.csv as settled credit. These messages simply confirm. No additional adjustment needed beyond what the event record shows.

---

**S. Prize Proceeds Confirmed Received**

| Message | User | Request | Linked Event |
|---|---|---|---|
| message_17 | user_24 | — | event_2165 |
| message_28 | user_38 | — | event_3491 |
| message_75 | user_101 | request_101 | event_9420 |
| message_88 | user_115 | request_115 | event_10699 |
| message_99 | user_129 | request_129 | event_11925 |
| message_110 | user_143 | — | event_13207 |

> Rule: The associated event already records this as settled income. These messages confirm. No additional adjustment.

---

**T. Prize Still In Processing — DO NOT COUNT**

| Message | User | Request | Platform |
|---|---|---|---|
| message_16 | user_23 | request_23 | DrawPay |
| message_71 | user_93 | request_93 | WinPoint |
| message_134 | user_170 | — | WinPoint (Bahasa) |
| message_209 | user_268 | — | PrizeLine |

---

### ⚠️ SCAM MESSAGES — COMPLETELY IGNORE

| Message | User | Text Summary |
|---|---|---|
| message_67 | user_88 | "Congratulations! You've been selected for a cash prize. Pay the release charge today to receive the funds immediately." |
| message_142 | user_179 | "Selamat! Anda terpilih untuk menerima hadiah uang tunai. Bayar biaya pencairan hari ini agar dana segera diterima." (Same pattern in Bahasa Indonesia) |

> [!CAUTION]
> These messages are advance-fee fraud (419 scam). They must be completely ignored.
> Do NOT reduce the user's balance for any "release fee". Do NOT add any "prize" as income.
> The message_67 references user_88 who has an investment_purchase event — unrelated.

---

### BANK MESSAGES

**U. Inter-Account Transfer — Net Zero**

| Message | User | Request | Notes |
|---|---|---|---|
| message_13 | user_18 | request_18 | Summit Bank — same account holder transfer |
| message_23 | user_33 | request_33 | Cedar Bank — same account holder transfer |
| message_41 | user_57 | request_57 | Summit Bank — same account holder |
| message_135 | user_171 | request_171 | Cedar Bank — same account holder |
| message_161 | user_202 | request_202 | Harbor Bank — two cards, two minimums |
| message_202 | user_261 | request_261 | Summit Bank — same account holder |
| message_213 | user_273 | request_273 | Harbor Bank — two accounts (Bahasa) |

> Rule: Both legs of the transfer will appear in events. They cancel each other. Net cash effect = 0. Both remain visible in history but neither counts as external income or expense.

**Exception:** message_136 and message_161 — TWO SEPARATE CARD MINIMUMS. These are NOT inter-account transfers. Each minimum payment debit is independent and both must be counted.

---

**V. Card Charge Under Investigation — Keep Debit (No Reversal Yet)**

| Message | User | Request | Linked Event |
|---|---|---|---|
| message_106 | user_138 | — | event_12709 |
| message_121 | user_156 | — | event_14399 |
| message_157 | user_198 | request_198 | event_18269 |
| message_164 | user_210 | request_210 | event_19334 |
| message_183 | user_234 | request_234 | event_21582 |
| message_197 | user_252 | request_252 | event_23203 (Bahasa) |

> Rule: Dispute is open but no reversal posted. Keep the original debit in cashflow. Do NOT add a reversal credit.

---

**W. Failed Debit, Will Retry**

| Message | User | Request | Linked Event |
|---|---|---|---|
| message_69 | user_91 | request_91 | event_8575 |
| message_179 | user_229 | — | event_21101 |
| message_198 | user_253 | request_253 | event_23306 |
| message_201 | user_259 | request_259 | event_23855 |

> Rule: The original debit event is `failed`, but the bill is still outstanding. Continue to reserve the amount as a pending debit obligation. Another attempt will be made.

---

### EXPENSE AMENDMENTS

**X. Rent Increase 12%**

| Message | User | Request | Notes |
|---|---|---|---|
| message_12 | user_16 | request_16 | StayLedger — from next rent payment |
| message_51 | user_69 | — | RentNest — from next rent payment |
| message_55 | user_73 | — | RentTrack — from next rent payment |
| message_61 | user_81 | request_81 | StayLedger — from next rent payment |
| message_105 | user_137 | — | HomePortal — from next rent payment |
| message_147 | user_185 | request_185 | HomePortal — from next rent payment |
| message_175 | user_225 | request_225 | HomePortal — 12% increase (Bahasa) |

> Rule: From the next rent due date, apply 12% increase to the user's recurring rent event amount. Future recurring rent = current_rent × 1.12.

---

**Y. Work Expense Reimbursement**

| Message | User | Request | Linked Event |
|---|---|---|---|
| message_117 | user_152 | — | event_14026 |
| message_150 | user_188 | request_188 | event_17401 |
| message_174 | user_224 | — | event_20615 (Bahasa) |

> Rule: The linked event is already a settled income credit (work_expense reimbursement). These messages confirm the claim is closed. No further reimbursement expected.

---

**Z. Payroll-Confirmed Salary (Bahasa Indonesia)**

| Message | User | Notes |
|---|---|---|
| message_02 | user_03 | Regular payroll confirmed — OCR payslip for amount |

> Rule: Next payslip will show regular salary. Confirmed via image_01 OCR: IDR 4,365,000.

---

## 3. Message Processing Decision Table

| Message Effect | Action |
|---|---|
| Salary increase | Override `income.amount` for all future cycles from `from_date` |
| Salary decrease (temp) | Reduce next cycle only; restore thereafter |
| Employment ended | Remove income stream after last confirmed salary |
| First salary | Add single credit at confirmed date; extrapolate recurrence |
| Date shifted | Move next income settlement_date |
| Commission excluded | Use base only; exclude commission event from income |
| Arrears (one-time) | Add single credit equal to arrears in next cycle |
| Invoice approved | Add single credit at stated settlement date |
| Gig payout pending | Exclude |
| Refund pending | Exclude |
| FX refund processing | Exclude |
| Investment valuation | Ignore |
| Investment sale settled | Already in events (settled) |
| Prize confirmed | Already in events (settled) |
| Prize processing | Exclude |
| Scam | Completely ignore |
| Inter-account transfer | Net 0; both legs in events |
| Two card minimums | Both debits independent |
| Dispute open, no reversal | Keep original debit |
| Failed debit retry | Reserve as pending debit |
| Rent +12% | Increase next rent by 1.12× |
| Work expense reimbursement | Already in events (settled) |
| FX charge, amount TBD | Keep debit; use exchange rate at settlement |

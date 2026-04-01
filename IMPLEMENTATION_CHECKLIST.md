# Implementation Checklist — MSM_Pro Sprint 3
**Phase:** P0 Core (April 1-30)
**Owner:** Development Team + Maikeo
**Last Updated:** 2026-03-29

---

## Pre-Sprint Setup (This Week)

### Decisions from Maikeo ✓ Must Complete
- [ ] Maikeo confirms Morning Routine is #1 pain
- [ ] Maikeo confirms repricing automation in April (not May)
- [ ] Maikeo confirms confidence 70%+ acceptable
- [ ] Maikeo confirms SaaS long-term goal
- [ ] Maikeo approves 2-week timeline
- [ ] Maikeo validates success metrics

### Team Setup ✓ Must Complete
- [ ] Dev team reads ACTION_PLAN.md (30 min)
- [ ] Frontend team assigned to Tasks 1.1, 1.2, 1.3
- [ ] Backend team assigned to Tasks 2.1, 2.2
- [ ] QA team assigned to Task 2.3 (testing)
- [ ] PM schedules daily standups (10 min, 2pm BRT)
- [ ] Slack channel created: #msm-pro-sprint3

### Technical Setup ✓ Must Complete
- [ ] Railway dashboard accessible
- [ ] GitHub branch created: `feature/sprint-3`
- [ ] Docker development environment runs locally
- [ ] Database migrations tested (`alembic current` works)
- [ ] Test environment ready (pytest runs, >10% baseline coverage)
- [ ] Sentry monitoring enabled
- [ ] Frontend build runs locally (`npm run dev` works)

### Communication Setup ✓ Must Complete
- [ ] Maikeo added to Slack channel
- [ ] Weekly sync scheduled (Friday 4pm BRT)
- [ ] Demo day set (Friday end of sprint)
- [ ] Blockers documented in shared doc
- [ ] Success criteria printed/shared

---

## Week 1: UX Foundation (April 1-7)

### Task 1.1: Morning Routine Card (Frontend) — 3 days
**Owner:** Frontend Dev 1

#### Design Phase
- [ ] Review UX_RECOMMENDATIONS.md Section 3 (mockups)
- [ ] Create high-fidelity Figma designs (3 card variations: red/yellow/green)
- [ ] Share with team for feedback
- [ ] Incorporate feedback (1-2 iterations)
- [ ] Finalize component design
- [ ] Create design tokens (colors, spacing, typography)

#### Development Phase
- [ ] Component structure planned (parent container, child cards)
- [ ] API integration decided (which endpoint provides data?)
- [ ] State management planned (Zustand vs React Context?)
- [ ] TypeScript types defined
- [ ] Component implementation (responsive, dark mode)
- [ ] Styling with Tailwind (copy from designs)
- [ ] Performance optimized (<500ms render)
- [ ] Mobile responsive tested

#### Testing & QA
- [ ] Visual regression tests (Percy or Chromatic)
- [ ] Responsive test (desktop 1920px, tablet 768px, mobile 375px)
- [ ] Accessibility audit (a11y)
- [ ] Component storybook entry created
- [ ] 50%+ unit test coverage for component

#### Merge Criteria
- [ ] Code review approved (2+ reviewers)
- [ ] All tests passing
- [ ] No console errors/warnings
- [ ] Performance <500ms
- [ ] Accessible (WCAG AA)

**Success Criteria:**
- [ ] Card displays on top of dashboard
- [ ] Shows red/yellow/green based on data
- [ ] Specific actions recommended (not generic)
- [ ] Modal opens when clicking action
- [ ] Mobile responsive

**Blockers to Watch:**
- Design not finalized in time (add Figma buffer)
- API endpoint missing (backend dependency)
- Performance issues with re-renders (optimize context)

---

### Task 1.2: Dashboard Redesign (Frontend + Design) — 2 days
**Owner:** Frontend Dev 2 + Designer

#### Information Architecture
- [ ] List what currently exists (16 modules visible)
- [ ] Classify by importance: CRITICAL vs NICE-TO-HAVE
- [ ] Plan what hides (Perguntas, Reputação, Atendimento → tabs)
- [ ] Plan what shows (KPI cards, Anúncios table, Morning Routine)
- [ ] Create wireframe of new layout
- [ ] Share with Maikeo for feedback

#### Design Phase
- [ ] Redesign dashboard layout (Figma)
- [ ] Plan tab/drawer structure (where do hidden modules go?)
- [ ] Design collapsed KPI cards (space efficient)
- [ ] Design anúncios table layout (simplified)
- [ ] Coordinate with Task 1.1 (Morning Routine placement)

#### Development Phase
- [ ] Update router/layout structure
- [ ] Hide modules (conditional rendering)
- [ ] Add tabs/drawer component for hidden modules
- [ ] Reorganize KPI cards layout
- [ ] Update responsive breakpoints
- [ ] Style refinements

#### Performance
- [ ] Measure load time before (baseline: 3+s)
- [ ] Optimize bundle size (lazy load tabs)
- [ ] Optimize images (progressive load)
- [ ] Target load time: <2s (goal: 50% improvement)

#### Testing
- [ ] Functional test (all tabs accessible)
- [ ] Performance test (load time <2s)
- [ ] Accessibility test (tab order correct)
- [ ] Responsive test (all screen sizes)
- [ ] Cross-browser test (Chrome, Firefox, Safari)

**Success Criteria:**
- [ ] Dashboard loads <2 seconds
- [ ] 5 KPI metrics visible above fold
- [ ] Fewer than 10 visual elements visible initially
- [ ] Hidden modules accessible via tabs
- [ ] Mobile responsive

---

### Task 1.3: KPI Backend Optimization (Backend) — 1 day
**Owner:** Backend Dev 1

#### Endpoint Verification
- [ ] Endpoint `/api/v1/kpi/summary` exists and returns data
- [ ] Endpoint `/api/v1/kpi/summary?period=1d&compare=7d` exists
- [ ] Response includes: revenue, conversions, stock, visits, margins
- [ ] Response includes variation % (vs previous period)

#### Database Optimization
- [ ] Query uses `COUNT(DISTINCT listing_id)` (not snapshots)
- [ ] Query is indexed properly (listing_id, user_id)
- [ ] Query response time <500ms with 50 listings
- [ ] Add Redis cache (5 min TTL) for KPI
- [ ] Monitor slow queries (log if >1s)

#### Data Accuracy
- [ ] KPI numbers match actual data
- [ ] Variation calculations correct: (today - yesterday) / yesterday × 100
- [ ] Edge case: what if yesterday = 0? (handle division by zero)
- [ ] Edge case: new listing (no historical data)
- [ ] Test with real Maikeo data

#### API Documentation
- [ ] Document response schema
- [ ] Document parameter options (period: 1d, 7d, 30d, etc.)
- [ ] Document cache behavior
- [ ] Add to API docs `/docs`

#### Testing
- [ ] Unit tests for KPI calculations
- [ ] Integration tests with real DB
- [ ] Performance tests (load time with 50+ listings)
- [ ] Edge case tests (zero values, negative, missing data)
- [ ] 20%+ test coverage increase

**Success Criteria:**
- [ ] Endpoint returns correct data in <500ms
- [ ] Variation % calculated correctly
- [ ] Caching reduces response time 50%+
- [ ] Zero "off by 1" errors
- [ ] Handles edge cases gracefully

---

## Week 2: Repricing Automation (April 8-14)

### Task 2.1: Repricing Automaton Backend (Backend) — 5 days
**Owner:** Backend Dev 2

#### API Endpoint Implementation
- [ ] Endpoint `POST /api/v1/listings/{mlb_id}/reprice` created
- [ ] Receives: mlb_id, suggested_price, confidence_score
- [ ] Validates confidence >70% (or configurable threshold)
- [ ] Applies price via ML API (actual call, not local)
- [ ] Logs change to `price_change_logs` table
- [ ] Returns: success, new price, confirmation

#### ML API Integration (Real Repricing)
- [ ] Uses ML API endpoint `/items/{item_id}` (PUT to update)
- [ ] Handles ML OAuth token refresh (6h expiry)
- [ ] Retry logic with backoff (network failures)
- [ ] Rate limiting respected (1 req/sec)
- [ ] Error handling (price too high, not allowed, etc.)

#### Automation Scheduler (Celery)
- [ ] Celery task created: `calculate_and_apply_repricing`
- [ ] Runs every 6 hours (2am, 8am, 2pm, 8pm BRT)
- [ ] For each listing of user:
  - [ ] Calculate price suggestion (via existing service)
  - [ ] If confidence >70%:
    - [ ] Check safety rules (see below)
    - [ ] Apply via ML API
    - [ ] Log change
  - [ ] If confidence <70%:
    - [ ] Save as pending (show in UI for user to approve)
- [ ] Rate limit: max 5 repricings per listing per day
- [ ] Respect user settings (enable/disable repricing)

#### Safety Rules (Guardrails)
- [ ] Never increase >20% in 1 day (prevent price wars)
- [ ] Never go below minimum margin (protect profitability)
- [ ] Check stock (don't sell if 0 units)
- [ ] Check competitor moved price (disable repricing if yes)
- [ ] Respect price history (don't yo-yo wildly)
- [ ] Log every decision (why repriced, why not)

#### Data Structures
- [ ] Extend `Listing` model:
  - [ ] `repricing_enabled: bool` (toggle on/off)
  - [ ] `min_price: Decimal` (minimum allowed)
  - [ ] `max_price: Decimal` (maximum allowed)
- [ ] Create `PriceChangeLog` model (if not exists):
  - [ ] `listing_id, old_price, new_price, reason, applied_at`
- [ ] Update `ListingSnapshot`:
  - [ ] Add `suggested_price, confidence_score`

#### Testing
- [ ] Unit tests: safety rules (20 test cases)
- [ ] Unit tests: price calculation
- [ ] Integration tests: ML API calls (mock)
- [ ] Integration tests: Celery task execution
- [ ] Scenario tests: edge cases (zero stock, low margin, etc.)
- [ ] Target coverage: 30%+

**Success Criteria:**
- [ ] Repricing applies via ML API (not just backend)
- [ ] Safety rules prevent dangerous price changes
- [ ] Scheduling works (Celery task runs)
- [ ] Logging tracks all changes
- [ ] Zero unintended price changes in testing

**Deployment Readiness:**
- [ ] Migration created for new DB fields
- [ ] Rollback plan documented (revert to manual pricing)
- [ ] Monitoring setup (Sentry alerts if repricing fails)

---

### Task 2.2: Repricing UX Frontend (Frontend) — 2 days
**Owner:** Frontend Dev 1

#### Settings Panel
- [ ] Create settings UI for repricing (enable/disable toggle)
- [ ] Input fields: min_price, max_price
- [ ] Confidence threshold selector (70%, 75%, 80%, 85%, 90%)
- [ ] Save settings button
- [ ] Per-listing settings (override global)

#### Suggestion Modal
- [ ] Modal displays when repricing suggestion available
- [ ] Shows: "System suggests increasing MLB-XXX from R$ 189 to R$ 209"
- [ ] Displays confidence %: "Confidence: 82%"
- [ ] Displays reason: "Conversions declining 0.2pp, increasing price may recover"
- [ ] Displays estimated impact: "Estimated +R$ 50/week"
- [ ] Buttons: [Apply Now] [A/B Test] [Ignore] [Learn More]

#### History/Audit Trail
- [ ] Page showing all repricing actions
- [ ] Columns: Date, MLB, Old Price, New Price, Confidence, Result
- [ ] Filter by status (applied, pending, rejected)
- [ ] Sort by date, impact
- [ ] Show conversion/sales before/after repricing
- [ ] Calculate: "If repriced on Day X, would have gained +R$ Y"

#### A/B Testing Interface
- [ ] Option to A/B test instead of full repricing
- [ ] Configuration:
  - [ ] Price A (current or suggested)
  - [ ] Price B (alternative)
  - [ ] Duration (7d, 14d, 30d)
  - [ ] Split (50/50 or custom)
- [ ] Results dashboard:
  - [ ] Conversion rate comparison
  - [ ] Revenue comparison
  - [ ] Confidence interval
  - [ ] Recommendation (which price won)
- [ ] One-click apply winner

#### Notifications
- [ ] Toast when repricing applied: "✓ Price updated to R$ 209"
- [ ] Toast on error: "✗ Failed to update price. Try again?"
- [ ] Bell icon showing pending repricing suggestions
- [ ] Badge count on repricing module

#### Testing
- [ ] Modal interaction tests (all buttons)
- [ ] Form validation (price ranges)
- [ ] History pagination (100+ changes)
- [ ] A/B test math accuracy (split, confidence)
- [ ] Accessibility (form labels, keyboard nav)

**Success Criteria:**
- [ ] User sees suggestion and understands confidence %
- [ ] User can apply, ignore, or A/B test
- [ ] History shows audit trail
- [ ] Retrospective impact calculation shown
- [ ] Mobile responsive

---

### Task 2.3: Testing & Validation (QA + Backend) — 3 days
**Owner:** QA Lead + Backend Dev 2

#### Integration Testing
- [ ] Full flow: reprice triggered → API called → price changed on ML → logged
- [ ] Test with real Maikeo account (or test account)
- [ ] Test with 3-5 listings (small set first)
- [ ] Verify prices actually changed on ML (check manually)
- [ ] Verify logs captured changes correctly

#### Safety Rule Validation
- [ ] Rule 1: Never >20% increase — test with R$ 100→ R$ 125 (OK), R$ 100→R$ 150 (blocked)
- [ ] Rule 2: Minimum margin — test with margin 5% (blocked), 20% (OK)
- [ ] Rule 3: Stock check — test with 0 units (blocked), 10 units (OK)
- [ ] Rule 4: Competitor moved — disable repricing if rival price changed
- [ ] Rule 5: Price volatility — don't yo-yo (same price 2 days in a row)

#### Data Accuracy
- [ ] Repricing logs capture old_price, new_price, reason
- [ ] Suggested price matches confidence score calculation
- [ ] Confidence scores are calibrated (70% → high accuracy)
- [ ] Before/after metrics tracked (visits, sales, conversion)

#### Performance
- [ ] Repricing apply latency <2 sec (ML API + local validation)
- [ ] Celery task completes within SLA (finish within 10 min of run time)
- [ ] No database locks during repricing
- [ ] No impact on other operations (non-blocking)

#### Edge Cases
- [ ] What if user has 50+ listings? (Performance test)
- [ ] What if repricing fails midway? (Rollback/retry)
- [ ] What if ML API returns error? (Graceful degradation)
- [ ] What if price simultaneously changed by user? (Conflict handling)
- [ ] What if listing deleted mid-repricing? (Orphan handling)

#### Production Dry-Run
- [ ] Deploy to staging environment
- [ ] Run with test data (not live sales)
- [ ] Maikeo tests on staging before live
- [ ] Feedback documented
- [ ] Any blockers fixed before live

#### Documentation
- [ ] Write runbook: "How to debug repricing issues"
- [ ] Write troubleshooting: "Why didn't price change?"
- [ ] Create alert rules in Sentry (repricing failures)
- [ ] Document rollback procedure (if needed)

**Success Criteria:**
- [ ] 10+ repricing applications completed
- [ ] 100% of safety rules working correctly
- [ ] Zero unintended price changes
- [ ] Logs accurate and auditable
- [ ] Performance acceptable (no slowdowns)
- [ ] User confident in automation

---

## Week 3-4: Polish & Monitoring (April 15-30)

### Code Quality
- [ ] Code coverage: 20%+ (vs 2% baseline)
- [ ] All tests passing (zero failures)
- [ ] No console errors/warnings in dev/prod
- [ ] TypeScript strict mode no errors
- [ ] Linting clean (ESLint, Prettier)
- [ ] No security vulnerabilities (npm audit)

### Performance
- [ ] Dashboard load: <2 sec (vs 3+ before)
- [ ] Morning Routine card: <500ms
- [ ] Repricing endpoint: <2 sec
- [ ] Database queries optimized (indexes, no N+1)
- [ ] Redis caching working (KPI cache hits >90%)

### Monitoring
- [ ] Sentry alerts configured
- [ ] Error tracking active
- [ ] Performance monitoring (API latency)
- [ ] Uptime monitoring (status page)
- [ ] User activity logging (feature usage)

### Documentation
- [ ] README updated with new features
- [ ] API docs updated (/docs endpoint)
- [ ] Deployment guide updated
- [ ] Troubleshooting guide created
- [ ] Architecture diagram updated

### Maikeo Validation
- [ ] Weekly demo (Friday)
- [ ] Feedback collected
- [ ] Any issues filed as bugs
- [ ] Success metrics measured
- [ ] Decision: full rollout or iterate?

---

## Success Metrics (End of April)

### Product
- [ ] Morning Routine card:
  - [ ] Visible on every dashboard load
  - [ ] Shows 3+ actionable items
  - [ ] User feedback >4/5 (NPS)
- [ ] Dashboard:
  - [ ] Loads in <2 seconds
  - [ ] Maikeo: "Much clearer what to do"
  - [ ] Usage: 5x/week (vs 2x before)
- [ ] Repricing:
  - [ ] 10+ automatic repricing actions
  - [ ] 100% safety rule compliance
  - [ ] 5-8% margin increase on affected listings
  - [ ] Zero user complaints

### Technical
- [ ] Test coverage: 20%+ (goal: double the baseline)
- [ ] Sentry: <5 errors/day (unrelated to repricing)
- [ ] Uptime: 99.5%+
- [ ] Performance: p95 latency <500ms

### Business
- [ ] Maikeo: +R$ 3k/month (from repricing margain gains)
- [ ] Adoption: Repricing enabled on 50%+ listings
- [ ] Retention: Weekly active user 5x (high engagement)
- [ ] NPS: >50 (positive sentiment)

---

## Risk Mitigation

### Risk 1: Repricing breaks and loses sales
**Probability:** Low (safety rules)
**Impact:** High (money)
**Mitigation:**
- [ ] Safety rules tested thoroughly
- [ ] Pilot with 3-5 listings first
- [ ] Maikeo approval before each application
- [ ] Immediate rollback if issues detected

### Risk 2: Morning Routine card too complex
**Probability:** Medium (UX is hard)
**Impact:** Medium (adoption)
**Mitigation:**
- [ ] Mockups reviewed with Maikeo early
- [ ] 2-3 iterations on design
- [ ] Usability testing with 3+ users
- [ ] Fallback: simpler version if needed

### Risk 3: Timeline slips
**Probability:** Medium (always happens)
**Impact:** High (launches delayed)
**Mitigation:**
- [ ] Buffer 2 days in Week 3-4
- [ ] Daily standup keeps team aligned
- [ ] Scope negotiation ready (cut nice-to-haves)
- [ ] Parallel workstreams (tasks don't block each other)

### Risk 4: Team unavailable
**Probability:** Low
**Impact:** High
**Mitigation:**
- [ ] Cross-training (frontend can help backend on testing)
- [ ] Documented procedures (so cover is possible)
- [ ] Backup plan (delay Phase 2 if needed)

---

## Sign-Off

**Sprint 3 ready to start?**

- [ ] **Maikeo:** Approves decisions (section: "Decisions from Maikeo")
- [ ] **Frontend Lead:** Confirms team + timeline
- [ ] **Backend Lead:** Confirms team + timeline
- [ ] **QA Lead:** Confirms testing plan
- [ ] **PM:** All setup complete

**Date:** _____________
**Approved by:** _____________

---

## Weekly Status Template

**Week X Status (April Y):**
- [ ] Task 1.1: X% complete (blockers: ...)
- [ ] Task 1.2: X% complete (blockers: ...)
- [ ] Task 1.3: X% complete (blockers: ...)
- [ ] Task 2.1: X% complete (blockers: ...)
- [ ] Task 2.2: X% complete (blockers: ...)
- [ ] Task 2.3: X% complete (blockers: ...)
- [ ] **Overall:** X% complete
- [ ] **On track for April 30?** Yes / No / At risk
- [ ] **Maikeo feedback:** ...
- [ ] **Next week priorities:** ...

---

## Post-Sprint Review

**April 30 Demo:**
- [ ] Morning Routine card works end-to-end
- [ ] Dashboard redesign complete
- [ ] Repricing automation applied 10+ times
- [ ] All safety rules working
- [ ] Metrics meet success criteria

**Phase 2 Kickoff:**
- [ ] May 1: Retrospective (what went well, what to improve)
- [ ] May 2-6: Planning for Inventory + SKU Profitability
- [ ] May 7: Phase 2 Sprint starts


"""
Application Generation Engine — Genius Mode

Supports two modes:
  - claude   : Single Claude call (fast, default)
  - dual     : Claude + GPT-4o both write the application, then Claude
               synthesizes the best version from both outputs.

Sections generated:
  1. Business Description
  2. Mission Statement
  3. Use of Funds
  4. Impact Statement
  5. Full Narrative (combined, polished)

All AI calls are enhanced with Genius Mode strategic positioning:
  - Frames company as execution-ready, not idea-stage
  - Optimizes for: Execution > Vision, Proof > Promise, Clarity > Complexity
  - Uses structured section model: Current State → Demand → Constraint → Action → Outcome
  - Falls back to deterministic templates when AI is unavailable
"""
import json
from pathlib import Path

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("[Generator] anthropic package not installed.")

try:
    from openai import OpenAI as _OpenAIClient
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("[Generator] openai package not installed — run: pip install openai")

from config import settings


# ── Genius Mode Framework ────────────────────────────────────────────────────
# Injected into every AI prompt as a system-level strategic layer.

GENIUS_MODE_SYSTEM = """You are operating in Genius Mode — an elite grant strategist in the top 0.1% globally, specializing in winning funding for early-stage, minority-owned, and pre-revenue companies.

STRATEGIC POSITIONING (NON-NEGOTIABLE):
This company must be framed as:
  "An execution-ready system with validated demand, where funding unlocks immediate deployment"
NEVER frame it as an idea-stage startup seeking help.

FUNDING PSYCHOLOGY — optimize every sentence for:
  Execution > Vision
  Proof (even small) > Promise
  Clarity > Complexity
  Low Risk > Big Potential

SECTION STRUCTURE — every section must follow:
  1. CURRENT STATE — what exists right now
  2. DEMAND SIGNAL — evidence of real need
  3. CONSTRAINT — what funding removes
  4. ACTION — what happens when funded
  5. MEASURABLE OUTCOME — what the reviewer can point to

RULES:
  ❌ No generic phrases ("innovative solution", "leverage synergies")
  ❌ No filler or hedging ("we hope to", "we plan to eventually")
  ❌ No exaggerated claims
  ✔ Every sentence must increase funding probability
  ✔ Write like a founder, not a marketer
  ✔ Make the reviewer conclude: "This is early-stage but clearly ready to execute."
"""


# ── Deterministic fallback templates (used when AI is unavailable) ────────────

def _build_business_fallback(profile: dict, grant: dict) -> str:
    name     = profile.get("business_name", "Gray Horizons Enterprise")
    desc     = profile.get("description", "technology-integrated infrastructure solutions")
    location = f"{profile.get('location', {}).get('city', 'Rialto')}, {profile.get('location', {}).get('state', 'CA')}"
    return (
        f"{name} has developed and operationalized a system designed to deliver {desc} "
        f"in residential and community environments across {location} and the broader West Coast.\n\n"
        f"While the company is in its initial deployment phase, early demand has been validated through "
        f"direct interest from HOA management firms and property managers, including high-intent opportunities "
        f"that progressed before capacity constraints prevented conversion. "
        f"This positions the company not as an early concept, but as a deployment-ready system constrained "
        f"primarily by execution bandwidth rather than market demand."
    )


def _build_mission_fallback(profile: dict, grant: dict) -> str:
    name = profile.get("business_name", "Gray Horizons Enterprise")
    return (
        f"The mission of {name} is to deploy practical, working systems that improve how communities "
        f"manage infrastructure, communication, and daily operations. "
        f"Rather than prioritizing expansion through concept development, the company focuses on execution — "
        f"ensuring that each system implemented delivers measurable and sustained use. "
        f"Success is defined by adoption and real-world impact, not deployment alone."
    )


def _build_funds_fallback(profile: dict, grant: dict) -> str:
    amount    = grant.get("amount_max", 50000) or 50000
    base      = int(amount * 0.6)
    return (
        f"The base operational requirement for initial deployment is approximately ${base:,}. "
        f"The requested funding level of ${amount:,} is intentionally structured to accelerate scale "
        f"and reduce missed opportunities.\n\n"
        f"Core allocation:\n"
        f"• Initial deployment tools and infrastructure (40%)\n"
        f"• First wave of installations and client onboarding (35%)\n"
        f"• Operations and team capacity (25%)\n\n"
        f"Funding above the baseline enables parallel deployments instead of sequential execution, "
        f"faster conversion of existing demand, and reduced time between lead generation and deployment. "
        f"This transforms funding from enabling activity into accelerating momentum."
    )


def _build_impact_fallback(profile: dict, grant: dict) -> str:
    return (
        f"Within the first 3–6 months, funding enables conversion of existing demand into active deployments, "
        f"directly impacting early users and communities. Projected outcomes include initial system deployment "
        f"across multiple residential or HOA environments, measurable improvements in organization and "
        f"operational efficiency, and rapid iteration based on real-world usage.\n\n"
        f"Within 6–12 months, the model scales into broader adoption across similar environments, "
        f"increasing total impact significantly. This is a near-term execution model with compounding "
        f"results — not a long-term speculative initiative."
    )


def _build_narrative_fallback(profile: dict, grant: dict) -> str:
    name  = profile.get("business_name", "Gray Horizons Enterprise")
    gname = grant.get("name", "this grant")
    return (
        f"{name} is positioned at the transition point between system readiness and real-world deployment. "
        f"The infrastructure has been built. Market interest has been confirmed. "
        f"The limiting factor is execution capacity.\n\n"
        f"Without funding, growth occurs slowly and selectively — leading to missed opportunities with "
        f"clients who are ready to move but cannot be served at current capacity. "
        f"With {gname} funding, the company transitions immediately into active deployment, "
        f"capturing existing demand and establishing operational traction.\n\n"
        f"This creates a feedback loop: deployment leads to validation, validation leads to expansion, "
        f"and expansion increases long-term sustainability. Every dollar deployed here converts directly "
        f"into a real-world outcome — not a plan, not a prototype, but a running system.\n\n"
        f"This is not a request to validate an idea. It is a request to accelerate a system that is "
        f"already positioned to execute."
    )


def generate_fallback_application(grant: dict, profile: dict) -> dict:
    """
    Deterministic Genius Mode application — no AI required.
    Used when both Claude and OpenAI are unavailable.
    """
    biz     = _build_business_fallback(profile, grant)
    mission = _build_mission_fallback(profile, grant)
    funds   = _build_funds_fallback(profile, grant)
    impact  = _build_impact_fallback(profile, grant)
    narr    = _build_narrative_fallback(profile, grant)
    return {
        "business_description": biz,
        "mission_statement":    mission,
        "use_of_funds":         funds,
        "impact_statement":     impact,
        "full_narrative":       narr,
        "claude_text":          narr,
        "openai_text":          None,
        "synthesized_text":     None,
        "ai_mode":              "fallback",
    }


# ── Profile helper ────────────────────────────────────────────────────────────

def _load_profile() -> dict:
    profile_path = Path(__file__).parent.parent / "user_profile.json"
    if profile_path.exists():
        with open(profile_path) as f:
            return json.load(f)
    return {}


# ── AI callers ────────────────────────────────────────────────────────────────

def _call_claude(prompt: str, max_tokens: int = 800) -> str:
    """Call Claude (claude-sonnet-4-6) with Genius Mode system prompt."""
    if not ANTHROPIC_AVAILABLE:
        return "[Error: anthropic package not installed — pip install anthropic]"
    if not settings.anthropic_api_key:
        return "[Error: ANTHROPIC_API_KEY not set in .env]"
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=GENIUS_MODE_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()


def _call_openai(prompt: str, max_tokens: int = 800) -> str:
    """Call GPT-4o with Genius Mode system prompt."""
    if not OPENAI_AVAILABLE:
        return "[Error: openai package not installed — pip install openai]"
    if not settings.openai_api_key:
        return "[Error: OPENAI_API_KEY not set in .env]"
    client = _OpenAIClient(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": GENIUS_MODE_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


# ── Shared prompt builders ────────────────────────────────────────────────────

def _build_context(grant: dict, profile: dict) -> str:
    return f"""
BUSINESS PROFILE:
- Name: {profile.get('business_name', 'Our Business')}
- Type: {profile.get('business_type', 'LLC')}
- Industry: {profile.get('industry', 'Technology')}
- Founded: {profile.get('founded_year', 2020)}
- Employees: {profile.get('employees', 5)}
- Annual Revenue: ${profile.get('annual_revenue', 0):,}
- Location: {profile.get('location', {}).get('city', '')}, {profile.get('location', {}).get('state', '')}
- Ownership: {', '.join(profile.get('owner_demographics', []))}
- Mission: {profile.get('mission', '')}
- Description: {profile.get('description', '')}
- Use of Funds Template: {profile.get('use_of_funds_template', '')}
- Past Projects: {'; '.join(profile.get('past_projects', []))}

GRANT DETAILS:
- Grant Name: {grant.get('name', 'this grant')}
- Amount: ${grant.get('amount_max', 0):,} max
- Description: {(grant.get('description') or '')[:500]}
- Eligibility: {(grant.get('eligibility') or '')[:300]}
""".strip()


def _build_prompts(grant: dict, profile: dict) -> dict:
    ctx   = _build_context(grant, profile)
    gname = grant.get("name", "this grant")
    gamt  = grant.get("amount_max", 0)

    section_rule = """
Structure this section using the mandatory 5-part model:
1. CURRENT STATE — what the business has built or accomplished right now
2. DEMAND SIGNAL — concrete evidence of real market need (even small proof counts)
3. CONSTRAINT — the specific bottleneck that funding removes
4. ACTION — the exact steps taken once funded
5. MEASURABLE OUTCOME — a specific, believable result the reviewer can point to
Output only the section text — no headers, no labels."""

    return {
        "business_description": f"""{ctx}

Write a 2-paragraph business description for this grant application.
{section_rule}
This must feel like a founder writing it — grounded, decisive, execution-focused.
Emphasize that the system is BUILT and READY, not planned. Position any pre-revenue status
as a capacity constraint, not a viability question.""",

        "mission_statement": f"""{ctx}

Write a 1-paragraph mission statement aligned with "{gname}".
{section_rule}
It must feel authentic and specific — not a generic vision statement.
The reviewer should immediately understand: this company executes, not just aspires.""",

        "use_of_funds": f"""{ctx}

Write a specific "Use of Funds" section for "{gname}".
Total amount: ${gamt:,}.
{section_rule}
Break down allocation into realistic line items with percentages or dollar amounts.
Show clearly how funding removes the constraint and accelerates deployment.
Distinguish between base requirements and what additional funding unlocks.""",

        "impact_statement": f"""{ctx}

Write an impact statement for "{gname}".
{section_rule}
Quantify outcomes wherever possible — communities served, deployments completed,
efficiency gains, jobs supported. Use 3–6 month and 6–12 month time horizons.
This must read as a near-term execution model, not a long-term speculation.""",
    }


def _narrative_prompt(gname: str, business_desc: str, mission: str, funds: str, impact: str) -> str:
    return f"""Write the main narrative for a grant application for "{gname}".
Use the components below to build a cohesive, 4–5 paragraph narrative.

BUSINESS DESCRIPTION:
{business_desc}

MISSION STATEMENT:
{mission}

USE OF FUNDS:
{funds}

IMPACT STATEMENT:
{impact}

Narrative rules (Genius Mode):
- Open by establishing the company as execution-ready, not idea-stage
- Paragraph 2: concrete demand signal — proof that market need exists RIGHT NOW
- Paragraph 3: the constraint — what the reviewer's funding directly removes
- Paragraph 4: the action + outcome — what happens in the first 90 days after funding
- Close: make the reviewer feel this is low-risk, high-certainty, and fundable today
- Professional founder tone — never marketing copy
- Output only the narrative, no section labels or headers"""


# ── Single-AI (Claude) application ───────────────────────────────────────────

def generate_application(grant: dict, profile: dict = None) -> dict:
    """
    Generate a complete grant application using Claude + Genius Mode.
    Falls back to deterministic Genius Mode templates if Claude is unavailable.
    Returns: business_description, mission_statement, use_of_funds,
             impact_statement, full_narrative, ai_mode
    """
    if profile is None:
        profile = _load_profile()

    gname = grant.get("name", "this grant")
    print(f"[Generator] Claude + Genius Mode: {gname}")

    # Hard fallback — no API key or package
    if not ANTHROPIC_AVAILABLE or not settings.anthropic_api_key:
        print(f"[Generator] Claude unavailable — using Genius Mode fallback templates")
        return generate_fallback_application(grant, profile)

    prompts = _build_prompts(grant, profile)

    business_description = _call_claude(prompts["business_description"], max_tokens=600)
    mission_statement    = _call_claude(prompts["mission_statement"],    max_tokens=300)
    use_of_funds         = _call_claude(prompts["use_of_funds"],         max_tokens=400)
    impact_statement     = _call_claude(prompts["impact_statement"],     max_tokens=350)

    full_narrative = _call_claude(
        _narrative_prompt(gname, business_description, mission_statement, use_of_funds, impact_statement),
        max_tokens=1200
    )

    return {
        "business_description": business_description,
        "mission_statement":    mission_statement,
        "use_of_funds":         use_of_funds,
        "impact_statement":     impact_statement,
        "full_narrative":       full_narrative,
        "claude_text":          full_narrative,
        "openai_text":          None,
        "synthesized_text":     None,
        "ai_mode":              "claude",
    }


# ── Dual-AI application (Claude + GPT-4o + Synthesis) ────────────────────────

def generate_dual_application(grant: dict, profile: dict = None) -> dict:
    """
    Generate with Claude AND GPT-4o, then have Claude synthesize the best version.

    Returns everything from generate_application PLUS:
      - claude_text      : Claude's full narrative
      - openai_text      : GPT-4o's full narrative
      - synthesized_text : Claude's synthesized best-of-both narrative
      - claude_sections  : all 5 Claude sections
      - openai_sections  : all 5 GPT-4o sections
      - ai_mode          : 'dual'
    """
    if profile is None:
        profile = _load_profile()

    gname = grant.get("name", "this grant")
    print(f"[Generator] Dual-AI Genius Mode (Claude + GPT-4o): {gname}")

    if not ANTHROPIC_AVAILABLE or not settings.anthropic_api_key:
        print(f"[Generator] Claude unavailable — using Genius Mode fallback")
        return generate_fallback_application(grant, profile)

    prompts = _build_prompts(grant, profile)

    # ── Claude sections ────────────────────────────────────────────────────────
    print("[Generator]  → Claude: generating sections...")
    c_biz    = _call_claude(prompts["business_description"], max_tokens=600)
    c_miss   = _call_claude(prompts["mission_statement"],    max_tokens=300)
    c_funds  = _call_claude(prompts["use_of_funds"],         max_tokens=400)
    c_impact = _call_claude(prompts["impact_statement"],     max_tokens=350)
    c_narr   = _call_claude(
        _narrative_prompt(gname, c_biz, c_miss, c_funds, c_impact),
        max_tokens=1200
    )

    # ── GPT-4o sections ────────────────────────────────────────────────────────
    print("[Generator]  → GPT-4o: generating sections...")
    g_biz    = _call_openai(prompts["business_description"], max_tokens=600)
    g_miss   = _call_openai(prompts["mission_statement"],    max_tokens=300)
    g_funds  = _call_openai(prompts["use_of_funds"],         max_tokens=400)
    g_impact = _call_openai(prompts["impact_statement"],     max_tokens=350)
    g_narr   = _call_openai(
        _narrative_prompt(gname, g_biz, g_miss, g_funds, g_impact),
        max_tokens=1200
    )

    # ── Synthesis — Claude reads both and produces the best version ────────────
    print("[Generator]  → Claude: synthesizing best version...")
    synth_prompt = f"""You are a professional grant writer. You have two complete grant application narratives for "{gname}".
Your job is to synthesize the BEST possible final application narrative by:
1. Taking the strongest opening hook from either version
2. Combining the most compelling evidence, specifics, and data points
3. Using the most persuasive and authentic language
4. Ensuring the final narrative flows as one cohesive, winning application
5. Weaving in any unique insights that appear in only one version

--- CLAUDE VERSION ---
{c_narr}

--- GPT-4o VERSION ---
{g_narr}

Write the final synthesized narrative now. Output only the narrative text — no labels, no preamble."""

    synthesized = _call_claude(synth_prompt, max_tokens=1500)

    # Synthesize each section too
    def _synth_section(section_name: str, c_text: str, g_text: str, max_tok: int = 500) -> str:
        p = f"""Synthesize the best version of the {section_name} section from these two versions:

CLAUDE: {c_text}

GPT-4o: {g_text}

Output only the synthesized text."""
        return _call_claude(p, max_tokens=max_tok)

    print("[Generator]  → Synthesizing individual sections...")
    s_biz    = _synth_section("Business Description",  c_biz,    g_biz,    500)
    s_miss   = _synth_section("Mission Statement",     c_miss,   g_miss,   250)
    s_funds  = _synth_section("Use of Funds",          c_funds,  g_funds,  350)
    s_impact = _synth_section("Impact Statement",      c_impact, g_impact, 300)

    print(f"[Generator] Dual-AI complete for: {gname}")

    return {
        # Synthesized (default view) — used as the main application
        "business_description": s_biz,
        "mission_statement":    s_miss,
        "use_of_funds":         s_funds,
        "impact_statement":     s_impact,
        "full_narrative":       synthesized,

        # Raw per-model narratives (for comparison in dashboard)
        "claude_text":          c_narr,
        "openai_text":          g_narr,
        "synthesized_text":     synthesized,

        # Per-model sections (for detailed comparison tabs)
        "claude_sections": {
            "business_description": c_biz,
            "mission_statement":    c_miss,
            "use_of_funds":         c_funds,
            "impact_statement":     c_impact,
            "full_narrative":       c_narr,
        },
        "openai_sections": {
            "business_description": g_biz,
            "mission_statement":    g_miss,
            "use_of_funds":         g_funds,
            "impact_statement":     g_impact,
            "full_narrative":       g_narr,
        },

        "ai_mode": "dual",
    }


# ── Checklist ─────────────────────────────────────────────────────────────────

def generate_checklist(grant: dict) -> list[str]:
    """Generate a step-by-step application checklist for a grant."""
    grant_name = grant.get("name", "this grant")
    grant_url  = grant.get("url", "")
    amount     = grant.get("amount_max", 0)

    prompt = f"""Create a numbered step-by-step checklist to apply for "{grant_name}" (${amount:,}).
Grant URL: {grant_url}

Include:
1. Document preparation steps
2. Application form steps
3. Submission steps
4. Follow-up steps

Be specific and actionable. Format as a numbered list."""

    response = _call_claude(prompt, max_tokens=500)
    lines = [l.strip() for l in response.split("\n") if l.strip()]
    return lines

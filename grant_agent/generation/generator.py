"""
Application Generation Engine

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


# ── Profile helper ────────────────────────────────────────────────────────────

def _load_profile() -> dict:
    profile_path = Path(__file__).parent.parent / "user_profile.json"
    if profile_path.exists():
        with open(profile_path) as f:
            return json.load(f)
    return {}


# ── AI callers ────────────────────────────────────────────────────────────────

def _call_claude(prompt: str, max_tokens: int = 800) -> str:
    """Call Claude (claude-sonnet-4-6) and return response text."""
    if not ANTHROPIC_AVAILABLE:
        return "[Error: anthropic package not installed — pip install anthropic]"
    if not settings.anthropic_api_key:
        return "[Error: ANTHROPIC_API_KEY not set in .env]"
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()


def _call_openai(prompt: str, max_tokens: int = 800) -> str:
    """Call GPT-4o and return response text."""
    if not OPENAI_AVAILABLE:
        return "[Error: openai package not installed — pip install openai]"
    if not settings.openai_api_key:
        return "[Error: OPENAI_API_KEY not set in .env]"
    client = _OpenAIClient(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
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
    ctx = _build_context(grant, profile)
    gname = grant.get("name", "this grant")
    gamt = grant.get("amount_max", 0)
    return {
        "business_description": f"""{ctx}

Write a compelling 2-paragraph business description for this grant application.
Focus on: what the business does, who it serves, and why it matters.
Tone: professional, confident, community-focused.
DO NOT use filler phrases like "In conclusion" or "It is worth noting."
Output only the text, no labels.""",

        "mission_statement": f"""{ctx}

Write a 1-paragraph mission statement tailored to resonate with the goals of "{gname}".
It should feel authentic, specific, and inspiring — not generic.
Output only the mission statement text.""",

        "use_of_funds": f"""{ctx}

Write a specific, credible 1-paragraph "Use of Funds" statement for "{gname}".
Amount available: ${gamt:,}.
Break it down into realistic line items (percentages or dollar amounts).
Show how the funds directly advance the mission and create measurable outcomes.
Output only the text.""",

        "impact_statement": f"""{ctx}

Write a 1-paragraph impact statement for "{gname}".
Quantify the expected outcomes where possible (jobs created, people served, revenue growth).
Make it specific to the business and the grant's focus area.
Output only the impact statement text.""",
    }


def _narrative_prompt(gname: str, business_desc: str, mission: str, funds: str, impact: str) -> str:
    return f"""You are writing the main narrative section of a grant application for "{gname}".
Use the following components to write a cohesive, persuasive 4–5 paragraph narrative:

BUSINESS DESCRIPTION:
{business_desc}

MISSION STATEMENT:
{mission}

USE OF FUNDS:
{funds}

IMPACT STATEMENT:
{impact}

Rules:
- Open with a strong hook
- Weave the sections into a unified story
- Emphasize alignment with the grant's goals
- Close with a compelling call to action
- Professional but human tone
- Output only the narrative, no section labels"""


# ── Single-AI (Claude) application ───────────────────────────────────────────

def generate_application(grant: dict, profile: dict = None) -> dict:
    """
    Generate a complete grant application using Claude only.
    Returns: business_description, mission_statement, use_of_funds,
             impact_statement, full_narrative, ai_mode
    """
    if profile is None:
        profile = _load_profile()

    gname = grant.get("name", "this grant")
    print(f"[Generator] Claude-only: {gname}")

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
    print(f"[Generator] Dual-AI (Claude + GPT-4o): {gname}")

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

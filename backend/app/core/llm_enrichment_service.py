"""
LLM-Powered Enrichment Service

Intelligent enrichment that uses LLM to:
1. Plan search strategies based on property type
2. Analyze web pages to find contact info
3. Navigate through pages following relevant links
4. Extract and validate contact data

Steps are simple text for UI display as: Step1 → Step2 → Step3
"""

import logging
import re
import json
import time
import httpx
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote_plus

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class ExtractedContact:
    """Contact extracted by LLM."""
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    confidence: float = 0.0


@dataclass
class EnrichmentStep:
    """Detailed enrichment step with output and reasoning."""
    action: str  # e.g., "search_google", "verify_match", "extract_contact"
    description: str  # Human-readable description
    output: Optional[str] = None  # What was found/result
    reasoning: Optional[str] = None  # Why/verification reasoning
    status: str = "success"  # "success", "failed", "skipped"
    confidence: Optional[float] = None  # Confidence score if applicable
    url: Optional[str] = None  # Resource URL (search URL, website, etc.)
    source: Optional[str] = None  # Source name (apartments.com, Google Places, etc.)
    
    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "description": self.description,
            "output": self.output,
            "reasoning": self.reasoning,
            "status": self.status,
            "confidence": self.confidence,
            "url": self.url,
            "source": self.source,
        }
    
    def to_simple_string(self) -> str:
        """Convert to simple string for backwards compatibility."""
        parts = [self.description]
        if self.output:
            parts.append(self.output)
        if self.reasoning:
            parts.append(f"({self.reasoning})")
        return " ".join(parts)


@dataclass
class LLMEnrichmentResult:
    """Result from LLM-powered enrichment."""
    success: bool
    contact: Optional[ExtractedContact] = None
    management_company: Optional[str] = None
    management_website: Optional[str] = None
    management_phone: Optional[str] = None
    
    # Detailed steps with output and reasoning
    detailed_steps: List[EnrichmentStep] = field(default_factory=list)
    # Simple text steps for backwards compatibility
    steps: List[str] = field(default_factory=list)
    
    confidence: float = 0.0
    tokens_used: int = 0
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        # Generate simple steps from detailed steps if needed
        if not self.steps and self.detailed_steps:
            self.steps = [step.to_simple_string() for step in self.detailed_steps]
        
        return {
            "success": self.success,
            "contact": asdict(self.contact) if self.contact else None,
            "management_company": self.management_company,
            "management_website": self.management_website,
            "management_phone": self.management_phone,
            "steps": self.steps,
            "detailed_steps": [step.to_dict() for step in self.detailed_steps],
            "steps_display": " → ".join(self.steps) if self.steps else None,
            "confidence": self.confidence,
            "tokens_used": self.tokens_used,
            "error_message": self.error_message,
        }


# ============================================================
# LLM PROMPTS
# ============================================================

STRATEGY_PROMPT = """You are an expert at finding property manager contact information for commercial properties.

PROPERTY DATA:
- Address: {address}
- Type: {property_type}
- Owner (from records): {owner_name}

Based on the property type ({property_type}), I'm tailoring my search strategy to find decision-maker contacts.

Plan 8-12 diverse search strategies to find the property manager, leasing office, or management company contact.
BE THOROUGH - try multiple angles to CROSS-VALIDATE contacts:

1. PROPERTY NAME SEARCHES: Search for the property itself on listing sites
2. OWNER/COMPANY SEARCHES: Search for the owner company directly  
3. ADDRESS VARIATIONS: Try different address formats
4. MANAGEMENT COMPANY: Look for property management company
5. DIRECT WEBSITES: Try likely website URLs
6. LINKEDIN VALIDATION: Search for decision makers on LinkedIn
7. MULTIPLE SOURCES: Use different sites to verify the same contact

Return ONLY valid JSON (no markdown):
{{
  "strategies": [
    {{"action": "search_apartments_com", "query": "specific search"}},
    {{"action": "search_google", "query": "property name + city"}},
    {{"action": "search_google", "query": "owner company + property management"}},
    {{"action": "search_zillow", "query": "address search"}},
    {{"action": "search_yelp", "query": "property or management company"}},
    {{"action": "search_linkedin", "query": "company name property manager"}},
    {{"action": "search_linkedin", "query": "person name title company"}},
    {{"action": "visit_url", "url": "https://likely-website.com"}}
  ]
}}

Valid actions: search_apartments_com, search_google, search_zillow, search_yelp, search_linkedin, visit_url

IMPORTANT: 
- Generate at least 8 strategies with DIFFERENT queries and sources
- Include at least 2 LinkedIn searches to find and validate decision makers
- Use multiple sources for cross-validation (don't stop at first result)"""


ANALYZE_PAGE_PROMPT = """Extract ALL contact information from this webpage, PRIORITIZING DECISION-MAKERS.

TARGET PROPERTY: {address} ({property_type})
URL: {url}

PAGE CONTENT:
{content}

EXTRACT THOROUGHLY - FOCUS ON DECISION-MAKERS:
1. Look for named individuals with titles (Property Manager, Director, VP, Regional Manager, etc.)
2. Look for "Meet the Team", "Our Staff", "Leadership" sections
3. Look for phone numbers (prioritize direct lines over main office)
4. Look for email addresses (prioritize personal emails over generic ones)
5. Look for management company names and their contacts
6. Look for "Contact Us", "About", "Team" links to follow

DECISION-MAKER TITLES TO PRIORITIZE:
- Vice President, Director, Regional Manager, Owner (HIGHEST)
- Property Manager, Community Manager, Asset Manager (HIGH)
- Leasing Manager, General Manager, Operations Manager (MEDIUM)

Return ONLY valid JSON:
{{
  "is_correct_property": true/false,
  "property_name": "Name if found",
  "contacts_found": [
    {{"name": "Full Name", "title": "Their Title", "phone": "Direct Phone", "email": "Email", "is_decision_maker": true/false}}
  ],
  "management_company": "Company name if found",
  "management_phone": "Main phone if found",
  "management_email": "Main email if found",
  "links_to_follow": [{{"href": "/about", "reason": "Team page - likely has decision-maker contacts"}}]
}}

IMPORTANT:
- Extract EVERY named person you find, especially those with managerial titles
- Include title information to help identify decision-makers
- Prefer direct contact info over generic office numbers/emails"""


VERIFY_PLACE_PROMPT = """Verify if this Google Places result matches the target property address.

TARGET PROPERTY: {target_address}
GOOGLE PLACES RESULT:
- Name: {place_name}
- Address: {place_address}

Return ONLY valid JSON:
{{
  "is_correct_property": true/false,
  "confidence": 0.0-1.0,
  "reason": "Brief explanation"
}}

Consider: street number, street name, city, state. Allow small variations (e.g., "Ave" vs "Avenue", nearby numbers)."""


SELECT_CONTACT_PROMPT = """Select the BEST DECISION-MAKER contact from collected data for this property.

TARGET PROPERTY: {address}

COLLECTED DATA FROM MULTIPLE SOURCES:
{collected_data}

VALIDATION SUMMARY:
{validation_summary}

SELECTION CRITERIA - PRIORITIZE DECISION MAKERS (in order):
1. Regional Manager, Director, VP with verified contact info
2. Property Manager, Community Manager with phone AND email
3. Leasing Manager, Office Manager with contact info  
4. Named contact found on multiple sources (cross-validated)
5. Leasing office with both phone AND email
6. Management company main contact with phone
7. Any verified phone/email associated with the property

DECISION-MAKER TITLES TO LOOK FOR:
- Vice President, Director, Regional Manager (highest priority)
- Property Manager, Community Manager, Asset Manager
- Leasing Manager, Leasing Director
- General Manager, Operations Manager

CONFIDENCE SCORING:
- 0.9-1.0: Named person found on 2+ sources with title confirming decision-maker role
- 0.7-0.9: Named person found on 1 source with decision-maker title
- 0.5-0.7: Generic leasing office contact or unnamed management contact
- 0.3-0.5: Phone/email only, no verification
- 0.0-0.3: Uncertain or unverified contact

Return ONLY valid JSON:
{{
  "selected_contact": {{
    "name": "Full Name",
    "title": "Their title/role", 
    "email": "Best email found",
    "phone": "Best phone found",
    "company": "Management company name"
  }},
  "confidence": 0.0-1.0,
  "verification": "Why this is the best DECISION-MAKER contact",
  "sources_validated": ["list", "of", "sources", "where", "contact", "was", "found"]
}}

IMPORTANT: Prefer a decision-maker with verified info over generic contact. Cross-reference data!"""


VALIDATE_LINKEDIN_PROMPT = """Verify if this LinkedIn search result matches a decision-maker for the target property.

TARGET PROPERTY: {address}
MANAGEMENT COMPANY: {company}
EXISTING CONTACT INFO:
- Name: {contact_name}
- Title: {contact_title}
- Phone: {contact_phone}
- Email: {contact_email}

LINKEDIN SEARCH RESULTS:
{linkedin_data}

Verify if any LinkedIn profile matches the contact and is a decision-maker for this property.

Return ONLY valid JSON:
{{
  "found_match": true/false,
  "matched_profile": {{
    "name": "Full Name from LinkedIn",
    "title": "Title from LinkedIn",
    "company": "Company from LinkedIn"
  }},
  "is_decision_maker": true/false,
  "decision_maker_level": "high/medium/low",
  "confidence": 0.0-1.0,
  "reasoning": "Why this is/isn't a decision maker for this property"
}}

Decision-maker levels:
- HIGH: VP, Director, Regional Manager, Owner
- MEDIUM: Property Manager, Community Manager, General Manager
- LOW: Leasing Agent, Office Staff"""


CROSS_VALIDATE_PROMPT = """Cross-validate contact information found across multiple sources.

TARGET PROPERTY: {address}

CONTACTS FOUND FROM DIFFERENT SOURCES:
{all_contacts}

Analyze which contacts appear across multiple sources and are most likely to be the actual decision-maker.

Return ONLY valid JSON:
{{
  "validated_contacts": [
    {{
      "name": "Name",
      "title": "Title",
      "phone": "Phone",
      "email": "Email",
      "company": "Company",
      "sources_found": ["Source1", "Source2"],
      "is_decision_maker": true/false,
      "validation_confidence": 0.0-1.0,
      "reasoning": "Why this contact is validated"
    }}
  ],
  "best_decision_maker": {{
    "name": "Name of best decision maker",
    "title": "Their title",
    "phone": "Phone",
    "email": "Email", 
    "company": "Company",
    "confidence": 0.0-1.0,
    "reasoning": "Why this is the best decision maker to contact"
  }}
}}

VALIDATION RULES:
1. Same phone/email on 2+ sources = HIGH confidence
2. Same name on 2+ sources = MEDIUM confidence  
3. Decision-maker title increases confidence
4. Prefer contacts with both phone AND email"""


# ============================================================
# LLM ENRICHMENT SERVICE
# ============================================================

class LLMEnrichmentService:
    """LLM-powered intelligent enrichment service."""
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self.model = "openai/gpt-4o-mini"
        self.api_key = settings.OPENROUTER_API_KEY
        
    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
        return self._client
    
    async def enrich(
        self,
        address: str,
        property_type: str,
        owner_name: Optional[str] = None,
        lbcs_code: Optional[int] = None,
    ) -> LLMEnrichmentResult:
        """
        Main enrichment flow with simple step logging.
        """
        if not self.is_configured:
            return LLMEnrichmentResult(
                success=False,
                error_message="OpenRouter API key not configured",
                steps=["❌ API not configured"]
            )
        
        detailed_steps: List[EnrichmentStep] = []
        steps: List[str] = []  # For backwards compatibility
        tokens_used = 0
        collected_data: List[Dict[str, Any]] = []
        
        try:
            # ============ Step 1: Plan Strategy ============
            logger.info(f"  [LLM] Planning strategy for {address}")
            
            # Format property type for display
            property_type_display = property_type.replace("_", " ").title()
            
            detailed_steps.append(EnrichmentStep(
                action="plan_strategy",
                description=f"Analyzing property type: {property_type_display}",
                output=f"LLM selecting best sources for {property_type_display} properties",
                reasoning=f"Strategy tailored for {property_type_display} (apartments.com for residential, Yelp for commercial, etc.)",
                status="success"
            ))
            
            strategy_response, plan_tokens = await self._call_llm(
                STRATEGY_PROMPT.format(
                    address=address,
                    property_type=property_type,
                    owner_name=owner_name or "Unknown",
                )
            )
            tokens_used += plan_tokens
            strategies = strategy_response.get("strategies", [])
            
            if not strategies:
                detailed_steps.append(EnrichmentStep(
                    action="plan_strategy",
                    description="No strategies found",
                    status="failed"
                ))
                # Generate simple steps from detailed_steps
                steps = [step.to_simple_string() for step in detailed_steps]
                return LLMEnrichmentResult(
                    success=False,
                    detailed_steps=detailed_steps,
                    steps=steps,
                    tokens_used=tokens_used,
                    error_message="LLM couldn't plan search strategy"
                )
            
            strategy_list = ", ".join([s.get("action", "").replace("_", " ") for s in strategies[:8]])
            detailed_steps[-1].output = f"Selected {len(strategies)} sources for {property_type_display}: {strategy_list}"
            
            # ============ Step 2: Execute Strategies ============
            # Execute MORE strategies - be persistent!
            max_strategies = min(len(strategies), 8)  # Try up to 8 strategies
            
            for strategy in strategies[:max_strategies]:
                action = strategy.get("action", "")
                query = strategy.get("query", address)
                
                if action == "search_apartments_com":
                    search_url = f"https://www.apartments.com/search/?query={quote_plus(query)}"
                    step = EnrichmentStep(
                        action="search_apartments_com",
                        description="Searching apartments.com",
                        status="success",
                        url=search_url,
                        source="apartments.com"
                    )
                    detailed_steps.append(step)
                    
                    result = await self._search_apartments_com(query, address, property_type)
                    if result:
                        if result.get("property_name"):
                            step.output = f"Found {result['property_name']}"
                            if result.get("source_url"):
                                step.url = result["source_url"]  # Use actual listing URL
                            if result.get("is_correct_property") is False:
                                step.reasoning = "Property name found but address doesn't match"
                                step.status = "failed"
                            else:
                                step.reasoning = "Property verified"
                        collected_data.append(result)
                        tokens_used += result.get("tokens_used", 0)
                    else:
                        step.status = "failed"
                        step.output = "No results found"
                        
                elif action == "search_google":
                    step = EnrichmentStep(
                        action="search_google",
                        description="Searching Google Places",
                        status="success",
                        source="Google Places"
                    )
                    detailed_steps.append(step)
                    
                    result = await self._search_google_places(query, address, property_type)
                    if result:
                        # Update step with source URL
                        if result.get("source_url"):
                            step.url = result["source_url"]
                        
                        # Only add if verified as correct property
                        if result.get("is_correct_property", False):
                            step.output = f"Found {result.get('property_name', 'property')}"
                            step.reasoning = result.get("verification_reason", "Address verified")
                            step.confidence = result.get("verification_confidence")
                            collected_data.append(result)
                            tokens_used += result.get("tokens_used", 0)
                        else:
                            step.status = "failed"
                            step.output = result.get("property_name", "Result found")
                            step.reasoning = result.get("verification_reason", "Address doesn't match target property")
                            step.confidence = result.get("verification_confidence", 0.0)
                        
                elif action == "visit_url":
                    url = strategy.get("url")
                    if url:
                        domain = urlparse(url).netloc
                        step = EnrichmentStep(
                            action="visit_url",
                            description=f"Visiting {domain}",
                            status="success",
                            url=url,
                            source=domain
                        )
                        detailed_steps.append(step)
                        
                        result = await self._visit_and_analyze(url, address, property_type)
                        if result:
                            step.output = result.get("property_name") or "Page analyzed"
                            if result.get("is_correct_property", False):
                                step.reasoning = "Page verified for target property"
                            else:
                                step.reasoning = "Page doesn't match target property"
                                step.status = "failed"
                            collected_data.append(result)
                            tokens_used += result.get("tokens_used", 0)
                        else:
                            step.status = "failed"
                            step.output = "Failed to analyze page"
                
                elif action == "search_yelp":
                    yelp_search_url = f"https://www.yelp.com/search?find_desc={quote_plus(query)}"
                    step = EnrichmentStep(
                        action="search_yelp",
                        description="Searching Yelp",
                        status="success",
                        url=yelp_search_url,
                        source="Yelp"
                    )
                    detailed_steps.append(step)
                    
                    result = await self._search_yelp(query, address, property_type)
                    if result:
                        if result.get("source_url"):
                            step.url = result["source_url"]  # Use actual business URL
                        if result.get("is_correct_property", False):
                            step.output = f"Found {result.get('property_name', 'business')}"
                            step.reasoning = "Business verified"
                            collected_data.append(result)
                            tokens_used += result.get("tokens_used", 0)
                        else:
                            step.status = "failed"
                            step.output = "No verified match found"
                    else:
                        step.status = "failed"
                        step.output = "No results found"
                
                elif action == "search_linkedin":
                    step = EnrichmentStep(
                        action="search_linkedin",
                        description="Searching LinkedIn (via Google)",
                        status="success",
                        source="LinkedIn/Google"
                    )
                    detailed_steps.append(step)
                    
                    result = await self._search_linkedin_company(query, address, property_type)
                    if result:
                        if result.get("source_url"):
                            step.url = result["source_url"]
                        if result.get("management_company"):
                            step.output = f"Found: {result['management_company']}"
                        else:
                            step.output = "Found company info"
                        collected_data.append(result)
                        tokens_used += result.get("tokens_used", 0)
                    else:
                        step.status = "failed"
                        step.output = "No LinkedIn company found"
                
                elif action == "search_zillow":
                    zillow_url = f"https://www.zillow.com/homes/{quote_plus(query)}"
                    step = EnrichmentStep(
                        action="search_zillow",
                        description="Searching Zillow",
                        status="success",
                        url=zillow_url,
                        source="Zillow"
                    )
                    detailed_steps.append(step)
                    
                    # Use visit_and_analyze on Zillow search results
                    result = await self._visit_and_analyze(zillow_url, address, property_type)
                    if result:
                        if result.get("source_url"):
                            step.url = result["source_url"]
                        if result.get("is_correct_property", False):
                            step.output = f"Found {result.get('property_name', 'property')}"
                            step.reasoning = "Property verified"
                            collected_data.append(result)
                            tokens_used += result.get("tokens_used", 0)
                        else:
                            step.status = "failed"
                            step.output = "No verified match found"
                    else:
                        step.status = "failed"
                        step.output = "No results found"
                
                # Track progress but DON'T stop early - continue gathering data for cross-validation
                verified_count = sum(
                    1 for d in collected_data 
                    if d.get("is_correct_property") and (
                        any(c.get("email") or c.get("phone") for c in d.get("contacts_found", [])) or
                        d.get("management_phone")
                    )
                )
                
                if verified_count > 0:
                    logger.info(f"  [LLM] Found {verified_count} verified sources, continuing to gather more for validation...")
            
            # ============ Step 2b: Fallback Strategies if no verified results ============
            verified_data = [d for d in collected_data if d.get("is_correct_property", False)]
            
            if not verified_data:
                logger.info(f"  [LLM] No verified results, trying fallback strategies...")
                
                # Fallback 1: Try owner-based search
                if owner_name and owner_name != "Unknown":
                    fallback_step = EnrichmentStep(
                        action="fallback_owner_search",
                        description=f"Fallback: Owner search '{owner_name[:25]}...'",
                        status="success",
                        source="Google Places (owner)"
                    )
                    detailed_steps.append(fallback_step)
                    
                    owner_query = f"{owner_name} property management contact"
                    result = await self._search_google_places(owner_query, address, property_type)
                    if result:
                        if result.get("management_phone") or result.get("contacts_found"):
                            fallback_step.output = f"Found via owner search"
                            collected_data.append(result)
                            tokens_used += result.get("tokens_used", 0)
                        else:
                            fallback_step.status = "failed"
                            fallback_step.output = "No contact info"
                    else:
                        fallback_step.status = "failed"
                        fallback_step.output = "No results"
                
                # Fallback 2: Try address-only search
                fallback_addr_step = EnrichmentStep(
                    action="fallback_address_search",
                    description="Fallback: Direct address search",
                    status="success",
                    source="Google Places (address)"
                )
                detailed_steps.append(fallback_addr_step)
                
                addr_result = await self._search_google_places(address, address, property_type)
                if addr_result:
                    if addr_result.get("management_phone") or addr_result.get("contacts_found"):
                        fallback_addr_step.output = "Found via address"
                        # For direct address search, mark as verified if address closely matches
                        addr_result["is_correct_property"] = True
                        collected_data.append(addr_result)
                        tokens_used += addr_result.get("tokens_used", 0)
                    else:
                        fallback_addr_step.status = "failed"
                        fallback_addr_step.output = "No contact info"
                else:
                    fallback_addr_step.status = "failed"
                    fallback_addr_step.output = "No results"
                
                # Fallback 3: Try generic property type search in area
                if property_type in ["multi_family", "retail", "office"]:
                    # Parse city from address
                    addr_parts = address.split(",")
                    city = addr_parts[1].strip() if len(addr_parts) > 1 else ""
                    
                    if city:
                        fallback_type_step = EnrichmentStep(
                            action="fallback_area_search",
                            description=f"Fallback: {property_type} in {city}",
                            status="success",
                            source="Google Places (area)"
                        )
                        detailed_steps.append(fallback_type_step)
                        
                        type_query = f"{property_type.replace('_', ' ')} leasing office {city}"
                        type_result = await self._search_google_places(type_query, address, property_type)
                        if type_result:
                            if type_result.get("management_phone"):
                                fallback_type_step.output = f"Found {type_result.get('property_name', 'property')}"
                                collected_data.append(type_result)
                                tokens_used += type_result.get("tokens_used", 0)
                            else:
                                fallback_type_step.status = "failed"
                                fallback_type_step.output = "No contact info"
                        else:
                            fallback_type_step.status = "failed"
                            fallback_type_step.output = "No results"
            
            # ============ Step 3: Filter and Cross-Validate Contacts ============
            # Filter out unverified results
            verified_data = [
                d for d in collected_data 
                if d.get("is_correct_property", False)
            ]
            
            if not verified_data:
                detailed_steps.append(EnrichmentStep(
                    action="filter_results",
                    description="Filtering verified results",
                    output=f"Searched {len(collected_data)} sources, none verified",
                    reasoning="No matches found that could be verified against property address",
                    status="failed"
                ))
                # Generate simple steps from detailed_steps
                steps = [step.to_simple_string() for step in detailed_steps]
                return LLMEnrichmentResult(
                    success=False,
                    detailed_steps=detailed_steps,
                    steps=steps,
                    tokens_used=tokens_used,
                    error_message=f"Tried {len(detailed_steps)} search strategies but could not find verified contact information"
                )
            
            filter_step = EnrichmentStep(
                action="filter_results",
                description="Filtering verified results",
                output=f"{len(verified_data)} verified sources",
                reasoning="Only using sources that match target property address",
                status="success"
            )
            detailed_steps.append(filter_step)
            
            # ============ Step 3b: Cross-Validate Contacts Across Sources ============
            # Extract all contacts from verified data for cross-validation
            all_contacts_for_validation = []
            for data in verified_data:
                source_name = data.get("source", "Unknown")
                
                # Add individual contacts
                for contact in data.get("contacts_found", []):
                    all_contacts_for_validation.append({
                        **contact,
                        "source": source_name,
                        "source_url": data.get("source_url")
                    })
                
                # Add management contact
                if data.get("management_phone") or data.get("management_email"):
                    all_contacts_for_validation.append({
                        "name": None,
                        "title": "Management Contact",
                        "phone": data.get("management_phone"),
                        "email": data.get("management_email"),
                        "company": data.get("management_company"),
                        "source": source_name,
                        "source_url": data.get("source_url")
                    })
            
            # Cross-validate if we have contacts from multiple sources
            validation_summary = "Single source verification"
            sources_validated = []
            
            if len(verified_data) > 1 and all_contacts_for_validation:
                cross_validate_step = EnrichmentStep(
                    action="cross_validate",
                    description="Cross-validating contacts across sources",
                    status="success",
                    source="Multi-source validation"
                )
                detailed_steps.append(cross_validate_step)
                
                try:
                    cross_val_response, cross_val_tokens = await self._call_llm(
                        CROSS_VALIDATE_PROMPT.format(
                            address=address,
                            all_contacts=json.dumps(all_contacts_for_validation, indent=2)[:4000]
                        )
                    )
                    tokens_used += cross_val_tokens
                    
                    validated_contacts = cross_val_response.get("validated_contacts", [])
                    best_dm = cross_val_response.get("best_decision_maker", {})
                    
                    if validated_contacts:
                        # Count how many contacts appear on multiple sources
                        multi_source = [c for c in validated_contacts if len(c.get("sources_found", [])) > 1]
                        cross_validate_step.output = f"{len(multi_source)} contacts verified on multiple sources"
                        cross_validate_step.reasoning = f"Found {len(validated_contacts)} unique contacts across {len(verified_data)} sources"
                        
                        if multi_source:
                            validation_summary = f"{len(multi_source)} contacts found on multiple sources"
                            sources_validated = list(set(
                                src for c in multi_source for src in c.get("sources_found", [])
                            ))
                        
                        # If we found a best decision maker through cross-validation, prioritize it
                        if best_dm and best_dm.get("confidence", 0) > 0.7:
                            cross_validate_step.output += f" | Best: {best_dm.get('name', 'Contact')} ({best_dm.get('title', 'Unknown')})"
                            cross_validate_step.confidence = best_dm.get("confidence")
                    else:
                        cross_validate_step.output = "No cross-validated contacts"
                        cross_validate_step.status = "partial"
                        
                except Exception as e:
                    logger.warning(f"  [LLM] Cross-validation error: {e}")
                    cross_validate_step.status = "failed"
                    cross_validate_step.output = "Cross-validation skipped"
            
            # ============ Step 3c: LinkedIn Decision-Maker Validation ============
            # If we have a management company, try to find decision makers on LinkedIn
            management_company = None
            for data in verified_data:
                if data.get("management_company"):
                    management_company = data["management_company"]
                    break
            
            if management_company:
                linkedin_val_step = EnrichmentStep(
                    action="linkedin_validation",
                    description=f"Validating decision-makers for {management_company[:30]}...",
                    status="success",
                    source="LinkedIn"
                )
                detailed_steps.append(linkedin_val_step)
                
                # Get any contact name we've found so far
                first_contact = next((c for c in all_contacts_for_validation if c.get("name")), {})
                
                linkedin_result = await self._search_linkedin_company(
                    f"{management_company} property manager director",
                    address,
                    property_type
                )
                
                if linkedin_result:
                    linkedin_val_step.url = linkedin_result.get("source_url")
                    tokens_used += linkedin_result.get("tokens_used", 0)
                    
                    # Try to validate if found person is decision maker
                    if linkedin_result.get("contacts_found"):
                        dm_contacts = [c for c in linkedin_result["contacts_found"] 
                                      if self._is_decision_maker_title(c.get("title", ""))]
                        if dm_contacts:
                            linkedin_val_step.output = f"Found {len(dm_contacts)} decision-maker(s)"
                            linkedin_val_step.reasoning = f"Titles: {', '.join(c.get('title', '') for c in dm_contacts[:3])}"
                            validation_summary += f" + {len(dm_contacts)} LinkedIn decision-makers"
                            # Add to verified data for final selection
                            linkedin_result["is_correct_property"] = True
                            verified_data.append(linkedin_result)
                        else:
                            linkedin_val_step.output = "Found contacts but no clear decision-makers"
                            linkedin_val_step.status = "partial"
                    else:
                        linkedin_val_step.output = "No direct contacts found"
                        linkedin_val_step.status = "partial"
                else:
                    linkedin_val_step.status = "failed"
                    linkedin_val_step.output = "LinkedIn search failed"
            
            # ============ Step 4: Select Best Decision-Maker Contact ============
            select_step = EnrichmentStep(
                action="select_contact",
                description="Selecting best decision-maker contact",
                status="success"
            )
            detailed_steps.append(select_step)
            
            final_response, select_tokens = await self._call_llm(
                SELECT_CONTACT_PROMPT.format(
                    address=address,
                    collected_data=json.dumps(verified_data, indent=2)[:4000],
                    validation_summary=validation_summary
                )
            )
            tokens_used += select_tokens
            
            selected = final_response.get("selected_contact", {})
            confidence = final_response.get("confidence", 0.0)
            verification = final_response.get("verification", "")
            sources_from_selection = final_response.get("sources_validated", [])
            
            # Get management info from verified sources (management_company may already be set above)
            management_website = None
            management_phone = None
            management_email = None
            
            for data in verified_data:
                if data.get("management_company") and not management_company:
                    management_company = data["management_company"]
                if data.get("source_url") and not management_website:
                    management_website = data["source_url"]
                if data.get("management_phone") and not management_phone:
                    management_phone = data["management_phone"]
                if data.get("management_email") and not management_email:
                    management_email = data["management_email"]
            
            # Build result
            contact = None
            contact_phone = selected.get("phone") or management_phone
            contact_email = selected.get("email") or management_email
            
            if selected and (contact_email or contact_phone):
                name = selected.get("name")
                contact = ExtractedContact(
                    name=name,
                    first_name=name.split()[0] if name and " " in name else name,
                    last_name=name.split()[-1] if name and " " in name else None,
                    email=contact_email,
                    phone=contact_phone,
                    title=selected.get("title"),
                    company=selected.get("company") or management_company,
                    confidence=confidence,
                )
                
                # Update select step with results
                output_parts = []
                if contact.phone:
                    output_parts.append(f"Phone: {contact.phone}")
                if contact.email:
                    output_parts.append(f"Email: {contact.email}")
                if contact.company:
                    output_parts.append(f"Company: {contact.company}")
                
                select_step.output = ", ".join(output_parts)
                select_step.reasoning = verification or f"Selected with {confidence:.0%} confidence"
                select_step.confidence = confidence
            
            if contact:
                # Build output with validation info
                output_text = f"{contact.name or 'Contact'}"
                if contact.title:
                    dm_level = self._get_decision_maker_level(contact.title)
                    if dm_level != "unknown":
                        output_text += f" ({contact.title} - {dm_level} decision-maker)"
                    else:
                        output_text += f" ({contact.title})"
                output_text += f" at {contact.company or 'property'}"
                
                # Include validation sources if available
                reasoning_text = verification
                if sources_from_selection:
                    reasoning_text += f" | Validated on: {', '.join(sources_from_selection[:3])}"
                elif len(verified_data) > 1:
                    reasoning_text += f" | Cross-referenced across {len(verified_data)} sources"
                
                detailed_steps.append(EnrichmentStep(
                    action="complete",
                    description="Contact found (validated)",
                    output=output_text,
                    reasoning=reasoning_text,
                    status="success",
                    confidence=confidence,
                    url=management_website,
                    source=management_company or "Property"
                ))
            else:
                select_step.status = "failed"
                select_step.output = "No contact extracted"
                detailed_steps.append(EnrichmentStep(
                    action="complete",
                    description="No contact extracted",
                    status="failed"
                ))
            
            # Generate simple steps from detailed_steps for backwards compatibility
            steps = [step.to_simple_string() for step in detailed_steps]
            
            return LLMEnrichmentResult(
                success=contact is not None,
                contact=contact,
                management_company=management_company or selected.get("company"),
                management_website=management_website,
                management_phone=management_phone or selected.get("phone"),
                detailed_steps=detailed_steps,
                steps=steps,  # Always populate steps
                confidence=confidence,
                tokens_used=tokens_used,
            )
                
        except Exception as e:
            logger.error(f"  [LLM] Error: {e}")
            import traceback
            traceback.print_exc()
            steps.append(f"Error: {str(e)[:50]}")
            
            return LLMEnrichmentResult(
                success=False,
                steps=steps,
                tokens_used=tokens_used,
                error_message=str(e),
            )
    
    # ============================================================
    # HELPER METHODS
    # ============================================================
    
    def _is_decision_maker_title(self, title: str) -> bool:
        """Check if a title indicates a decision-maker role."""
        if not title:
            return False
        
        title_lower = title.lower()
        
        # High-level decision makers
        high_level = [
            "vice president", "vp", "director", "regional manager",
            "owner", "principal", "partner", "ceo", "coo", "cfo",
            "president", "executive", "chief"
        ]
        
        # Property-level decision makers
        property_level = [
            "property manager", "community manager", "asset manager",
            "general manager", "operations manager", "site manager",
            "leasing manager", "leasing director", "apartment manager",
            "portfolio manager", "area manager"
        ]
        
        all_dm_titles = high_level + property_level
        
        for dm_title in all_dm_titles:
            if dm_title in title_lower:
                return True
        
        return False
    
    def _get_decision_maker_level(self, title: str) -> str:
        """Get the decision-maker level for prioritization."""
        if not title:
            return "unknown"
        
        title_lower = title.lower()
        
        # Highest priority
        if any(t in title_lower for t in ["vice president", "vp", "director", "regional", "owner", "principal", "president", "executive", "chief"]):
            return "high"
        
        # Medium priority
        if any(t in title_lower for t in ["property manager", "community manager", "asset manager", "general manager", "operations manager", "portfolio manager"]):
            return "medium"
        
        # Lower priority (but still decision-maker)
        if any(t in title_lower for t in ["leasing manager", "site manager", "area manager"]):
            return "low"
        
        return "unknown"
    
    # ============================================================
    # SEARCH METHODS
    # ============================================================
    
    async def _search_apartments_com(
        self,
        query: str,
        address: str,
        property_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Search apartments.com for property."""
        try:
            client = await self._get_client()
            search_url = f"https://www.apartments.com/search/?query={quote_plus(query)}"
            
            logger.info(f"  [LLM] Searching apartments.com: {query}")
            response = await client.get(search_url, follow_redirects=True)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find listing links
            listing_links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/apartments/' in href or '/apartment/' in href:
                    if href.startswith('/'):
                        href = f"https://www.apartments.com{href}"
                    listing_links.append(href)
            
            listing_links = list(set(listing_links))[:3]
            
            if not listing_links:
                return None
            
            # Visit first listing
            for url in listing_links:
                result = await self._visit_and_analyze(url, address, property_type)
                if result and result.get("is_correct_property"):
                    result["source"] = "apartments.com"
                    return result
            
            return None
            
        except Exception as e:
            logger.error(f"  [LLM] apartments.com error: {e}")
            return None
    
    async def _search_google_places(
        self,
        query: str,
        address: str,
        property_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Search using Google Places API."""
        if not settings.GOOGLE_PLACES_KEY:
            return None
        
        try:
            client = await self._get_client()
            
            # Text search
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {"query": query, "key": settings.GOOGLE_PLACES_KEY}
            
            response = await client.get(url, params=params)
            if response.status_code != 200:
                return None
            
            results = response.json().get("results", [])
            if not results:
                return None
            
            # Get details
            place = results[0]
            place_id = place.get("place_id")
            
            if place_id:
                details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                details_params = {
                    "place_id": place_id,
                    "fields": "name,formatted_phone_number,website,formatted_address",
                    "key": settings.GOOGLE_PLACES_KEY,
                }
                
                details_response = await client.get(details_url, params=details_params)
                if details_response.status_code == 200:
                    result = details_response.json().get("result", {})
                    
                    name = result.get("name")
                    place_address = result.get("formatted_address", "")
                    phone = result.get("formatted_phone_number")
                    website = result.get("website")
                    
                    # Verify with LLM that this place matches the target address
                    verification, verify_tokens = await self._call_llm(
                        VERIFY_PLACE_PROMPT.format(
                            target_address=address,
                            place_name=name or "",
                            place_address=place_address
                        )
                    )
                    
                    is_correct = verification.get("is_correct_property", False)
                    verification_confidence = verification.get("confidence", 0.0)
                    
                    # Return verification details even if failed (for UI display)
                    if not is_correct:
                        logger.info(f"  [LLM] Google Places result '{name}' does not match '{address}' (confidence: {verification_confidence:.2f})")
                        return {
                            "source": "google_places",
                            "property_name": name,
                            "property_address": place_address,
                            "is_correct_property": False,
                            "verification_confidence": verification_confidence,
                            "verification_reason": verification.get("reason", "Address doesn't match"),
                            "tokens_used": verify_tokens,
                        }
                    
                    logger.info(f"  [LLM] Verified Google Places match: '{name}' = '{address}' (confidence: {verification_confidence:.2f})")
                    
                    if phone or website:
                        data = {
                            "source": "google_places",
                            "property_name": name,
                            "property_address": place_address,
                            "management_phone": phone,
                            "source_url": website,
                            "is_correct_property": True,
                            "verification_confidence": verification_confidence,
                            "verification_reason": verification.get("reason", ""),
                            "contacts_found": [],
                            "tokens_used": verify_tokens,
                        }
                        
                        # Visit website if available
                        if website:
                            web_result = await self._visit_and_analyze(website, address, property_type)
                            if web_result:
                                data["management_company"] = web_result.get("management_company") or name
                                data["contacts_found"] = web_result.get("contacts_found", [])
                                data["tokens_used"] += web_result.get("tokens_used", 0)
                        
                        return data
            
            return None
            
        except Exception as e:
            logger.error(f"  [LLM] Google Places error: {e}")
            return None
    
    async def _search_yelp(
        self,
        query: str,
        address: str,
        property_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Search Yelp for business contact info."""
        try:
            client = await self._get_client()
            search_url = f"https://www.yelp.com/search?find_desc={quote_plus(query)}"
            
            logger.info(f"  [LLM] Searching Yelp: {query}")
            response = await client.get(search_url, follow_redirects=True)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for business listings
            business_links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/biz/' in href and not '/biz_photos/' in href:
                    if href.startswith('/'):
                        href = f"https://www.yelp.com{href}"
                    business_links.append(href)
            
            business_links = list(set(business_links))[:3]
            
            if not business_links:
                return None
            
            # Visit first business page
            for url in business_links:
                result = await self._visit_and_analyze(url, address, property_type)
                if result:
                    result["source"] = "yelp"
                    if result.get("is_correct_property"):
                        return result
            
            return None
            
        except Exception as e:
            logger.error(f"  [LLM] Yelp error: {e}")
            return None
    
    async def _search_linkedin_company(
        self,
        query: str,
        address: str,
        property_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Search for company info and decision-makers via Google/company websites."""
        try:
            if not settings.GOOGLE_PLACES_KEY:
                return None
            
            client = await self._get_client()
            
            # Search for management company directly
            company_query = f"{query} property management company"
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {"query": company_query, "key": settings.GOOGLE_PLACES_KEY}
            
            logger.info(f"  [LLM] Searching for management company: {company_query}")
            
            response = await client.get(url, params=params)
            if response.status_code != 200:
                return None
            
            results = response.json().get("results", [])
            if not results:
                return None
            
            # Get details for first result
            place = results[0]
            place_id = place.get("place_id")
            
            if place_id:
                details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                details_params = {
                    "place_id": place_id,
                    "fields": "name,formatted_phone_number,website,formatted_address",
                    "key": settings.GOOGLE_PLACES_KEY,
                }
                
                details_response = await client.get(details_url, params=details_params)
                if details_response.status_code == 200:
                    result = details_response.json().get("result", {})
                    
                    name = result.get("name")
                    phone = result.get("formatted_phone_number")
                    website = result.get("website")
                    company_address = result.get("formatted_address", "")
                    
                    if phone or website:
                        data = {
                            "source": "linkedin_company_search",
                            "management_company": name,
                            "management_phone": phone,
                            "source_url": website,
                            "company_address": company_address,
                            "is_correct_property": True,  # Management company doesn't need address verification
                            "contacts_found": [],
                            "tokens_used": 0,
                        }
                        
                        # Visit website if available to find contacts
                        if website:
                            web_result = await self._visit_and_analyze(website, address, property_type)
                            if web_result:
                                data["contacts_found"] = web_result.get("contacts_found", [])
                                data["tokens_used"] += web_result.get("tokens_used", 0)
                            
                            # Also try to find team/about/leadership pages
                            team_pages = [
                                f"{website.rstrip('/')}/team",
                                f"{website.rstrip('/')}/about",
                                f"{website.rstrip('/')}/leadership",
                                f"{website.rstrip('/')}/about-us",
                                f"{website.rstrip('/')}/our-team",
                                f"{website.rstrip('/')}/management",
                            ]
                            
                            for team_url in team_pages[:3]:  # Try first 3
                                try:
                                    team_result = await self._visit_and_analyze(team_url, address, property_type, depth=1)
                                    if team_result and team_result.get("contacts_found"):
                                        # Look for decision makers in team page
                                        dm_contacts = [
                                            c for c in team_result["contacts_found"]
                                            if self._is_decision_maker_title(c.get("title", ""))
                                        ]
                                        if dm_contacts:
                                            logger.info(f"  [LLM] Found {len(dm_contacts)} decision-makers on {team_url}")
                                            data["contacts_found"].extend(dm_contacts)
                                            data["tokens_used"] += team_result.get("tokens_used", 0)
                                            break  # Found decision makers, stop looking
                                except Exception:
                                    continue
                        
                        # Filter to prioritize decision-makers
                        if data["contacts_found"]:
                            # Sort by decision-maker level
                            def dm_priority(contact):
                                level = self._get_decision_maker_level(contact.get("title", ""))
                                return {"high": 0, "medium": 1, "low": 2, "unknown": 3}.get(level, 3)
                            
                            data["contacts_found"] = sorted(data["contacts_found"], key=dm_priority)
                        
                        return data
            
            return None
            
        except Exception as e:
            logger.error(f"  [LLM] LinkedIn company search error: {e}")
            return None
    
    async def _visit_and_analyze(
        self,
        url: str,
        address: str,
        property_type: str,
        depth: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """Visit URL and use LLM to extract contact info."""
        if depth > 1:
            return None
        
        try:
            client = await self._get_client()
            logger.info(f"  [LLM] Visiting: {url}")
            
            response = await client.get(url, follow_redirects=True)
            if response.status_code != 200:
                return None
            
            # Simplify HTML
            simplified = self._simplify_html(response.text)
            
            # LLM analyzes
            analysis, tokens = await self._call_llm(
                ANALYZE_PAGE_PROMPT.format(
                    address=address,
                    property_type=property_type,
                    url=url,
                    content=simplified[:6000]
                )
            )
            
            contacts = analysis.get("contacts_found", [])
            links = analysis.get("links_to_follow", [])
            
            result = {
                "source_url": url,
                "is_correct_property": analysis.get("is_correct_property", False),
                "property_name": analysis.get("property_name"),
                "contacts_found": contacts,
                "management_company": analysis.get("management_company"),
                "management_phone": analysis.get("management_phone"),
                "tokens_used": tokens,
            }
            
            # Follow contact links to find more info - especially decision-makers
            if links and depth < 2:  # Allow 2 levels deep
                # Prioritize team/about/leadership pages for decision-makers
                priority_pages = ["team", "about", "leadership", "staff", "management", "contact"]
                
                def link_priority(link):
                    href = link.get("href", "").lower()
                    reason = link.get("reason", "").lower()
                    for i, keyword in enumerate(priority_pages):
                        if keyword in href or keyword in reason:
                            return i
                    return len(priority_pages)
                
                sorted_links = sorted(links, key=link_priority)
                
                # Try more links to find decision-makers
                links_to_try = 4 if not contacts else 2
                found_decision_maker = False
                
                for link in sorted_links[:links_to_try]:
                    href = link.get("href")
                    if href:
                        if href.startswith("/"):
                            href = urljoin(url, href)
                        sub = await self._visit_and_analyze(href, address, property_type, depth + 1)
                        if sub:
                            # Merge contacts
                            if sub.get("contacts_found"):
                                result["contacts_found"].extend(sub["contacts_found"])
                                # Check if we found any decision-makers
                                for c in sub["contacts_found"]:
                                    if c.get("is_decision_maker") or self._is_decision_maker_title(c.get("title", "")):
                                        found_decision_maker = True
                            # Update management info if found
                            if sub.get("management_phone") and not result.get("management_phone"):
                                result["management_phone"] = sub["management_phone"]
                            if sub.get("management_company") and not result.get("management_company"):
                                result["management_company"] = sub["management_company"]
                            result["tokens_used"] += sub.get("tokens_used", 0)
                            
                            # Only stop early if we found a decision-maker with contact info
                            if found_decision_maker and (result.get("contacts_found") or result.get("management_phone")):
                                break
            
            return result
            
        except Exception as e:
            logger.error(f"  [LLM] Visit error: {e}")
            return None
    
    # ============================================================
    # HELPERS
    # ============================================================
    
    async def _call_llm(self, prompt: str) -> tuple[Dict[str, Any], int]:
        """Call LLM and return parsed JSON + token count."""
        try:
            client = await self._get_client()
            
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 1000,
                }
            )
            
            if response.status_code != 200:
                logger.error(f"  [LLM] API error: {response.status_code}")
                return {}, 0
            
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            tokens = data.get("usage", {}).get("total_tokens", 0)
            
            # Parse JSON
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```\w*\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            
            try:
                return json.loads(content), tokens
            except json.JSONDecodeError:
                logger.error(f"  [LLM] JSON parse failed")
                return {}, tokens
                
        except Exception as e:
            logger.error(f"  [LLM] Error: {e}")
            return {}, 0
    
    def _simplify_html(self, html: str) -> str:
        """Simplify HTML for LLM."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove noise
            for tag in soup.find_all(['script', 'style', 'meta', 'link', 'noscript', 'svg']):
                tag.decompose()
            
            parts = []
            
            # Title
            title = soup.find('title')
            if title:
                parts.append(f"TITLE: {title.get_text().strip()}")
            
            # Headings
            for h in soup.find_all(['h1', 'h2', 'h3'])[:5]:
                text = h.get_text().strip()
                if text:
                    parts.append(f"HEADING: {text}")
            
            # Contact links
            for a in soup.find_all('a', href=True):
                text = a.get_text().strip().lower()
                if text and len(text) < 30 and any(w in text for w in ['contact', 'about', 'team', 'staff']):
                    parts.append(f"LINK: {a.get_text().strip()} -> {a['href']}")
            
            # Body text
            body = soup.find('body')
            if body:
                body_text = body.get_text(separator=' ', strip=True)
                body_text = re.sub(r'\s+', ' ', body_text)
                parts.append(f"CONTENT: {body_text[:4000]}")
            
            return "\n".join(parts)
            
        except:
            return html[:4000]
    
    def _has_contact(self, collected_data: List[Dict]) -> bool:
        """Check if we found a contact with email or phone."""
        for data in collected_data:
            for contact in data.get("contacts_found", []):
                if contact.get("email") or contact.get("phone"):
                    return True
            if data.get("management_phone"):
                return True
        return False


# Singleton
llm_enrichment_service = LLMEnrichmentService()

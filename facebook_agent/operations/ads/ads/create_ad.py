import json
from urllib.parse import parse_qs, urlparse

from facebook_agent.graph import call_graph, check_required, error, validation_error
from facebook_agent.lead_safety import form_usage_problems
from facebook_agent.operations.ads.account_guard import (
    ADS_GET_RETRIES,
    NO_PAYMENT_AD,
    OPTIMIZATION_GOALS,
    PAUSED,
    account_path,
    ads_mode,
    checked_account,
    owned_object,
    with_meta_explanation,
)

CALLS_TO_ACTION = ("SIGN_UP", "LEARN_MORE", "SUBSCRIBE", "GET_QUOTE", "APPLY_NOW")
LEAD_ADS_LINK = "https://fb.me/"  # lien imposé par Meta pour une publicité Lead Ads
CREATIVE_ERROR = "Échec de la création du visuel (creative) de la publicité."
AD_ERROR = "Échec de la création de la publicité."
# Une campagne OUTCOME_TRAFFIC optimise les clics sur un lien : le post doit en contenir un vers un site
LINK_OBJECTIVE = "OUTCOME_TRAFFIC"
POST_LINK_FIELDS = "attachments{type,url,unshimmed_url}"
META_HOSTS = ("facebook.com", "fb.com", "fb.me", "fbcdn.net", "instagram.com", "messenger.com")
SHIM_HOSTS = ("l.facebook.com", "lm.facebook.com")  # redirection de Facebook vers le vrai lien (paramètre u)


def _host(url: str) -> str:
    """Host name of a URL, in lower case.

    Args:
        url: An http/https URL.

    Returns:
        The host (e.g. "www.example.com"), or "" when there is none.
    """
    return (urlparse(url).hostname or "").lower()


def _external_link(post: dict) -> str | None:
    """First link of the post's attachments that leads outside Facebook, or None.

    Args:
        post: Fields of the post read with GET /{post_id}?fields=attachments{type,url,unshimmed_url}.

    Returns:
        The URL (unshimmed_url, or the target of a l.facebook.com redirection), or None when the
        post only has text, photos or videos of Facebook.
    """
    for attachment in (post.get("attachments") or {}).get("data", []):
        for url in (attachment.get("unshimmed_url"), attachment.get("url")):
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            if _host(url) in SHIM_HOSTS:
                url = (parse_qs(urlparse(url).query).get("u") or [""])[0]
            host = _host(url)
            if host and not any(host == meta or host.endswith("." + meta) for meta in META_HOSTS):
                return url
    return None


@with_meta_explanation
def create_ad(ad_account_id: str, ad_set_id: str, name: str, access_token: str, post_id: str | None = None,
              page_id: str | None = None, lead_form_id: str | None = None, message: str | None = None,
              image_url: str | None = None, call_to_action: str = "SIGN_UP", page_token: str | None = None) -> dict:
    """Create an ad, always PAUSED, in an ad set of the account: from an existing post, or a Lead Ads ad.

    Refused before any request when AD_ACCOUNT_MODE is no_payment: Meta does not allow an ad on an
    account without a payment method (subcode 1359188); campaigns and ad sets stay possible there.
    Reads the ad account (money check, as in create_campaign), then the ad set
    (GET /{ad_set_id}?fields=account_id,status,campaign{objective}), which must belong to this
    account. The objective of its campaign chooses the creative:
    - OUTCOME_AWARENESS, OUTCOME_TRAFFIC, OUTCOME_ENGAGEMENT: an existing post of the page
      (object_story_id = post_id); nothing new is published. OUTCOME_ENGAGEMENT is the usual way
      to boost a post. For OUTCOME_TRAFFIC (clicks on a link), the post is read first with the
      Page token (GET /{post_id}?fields=attachments{type,url,unshimmed_url}) and must contain a
      link to a website (outside Facebook), otherwise Meta refuses the ad.
    - OUTCOME_LEADS: a Lead Ads ad (object_story_spec with page_id and link_data: message, link
      https://fb.me/ as Meta requires, image_url as picture, call_to_action {type, value
      {lead_gen_form_id}}); Facebook creates a hidden publication of the page for it. The form is
      read first with the Page token (GET /{lead_form_id}?fields=status,page): it must be ACTIVE
      and belong to page_id.
    Then sends POST /act_{id}/adcreatives, and POST /act_{id}/ads with the creative and
    status=PAUSED. If the ad is refused, the creative just created is deleted (DELETE
    /{creative_id}). The status cannot be chosen: no function of this project makes an ad ACTIVE.
    The reads of the account and of the objects are tried again (2 times at most) when Meta limits
    the number of calls of the account.

    Parameters:
        - Input-ad_account_id (str, mandatory): ID of the ad account, "act_<digits>" or "<digits>".
          Example: "act_AD_ACCOUNT_ID_EXAMPLE"
        - Input-ad_set_id (str, mandatory): ID of an ad set of this account (see list_ad_sets).
          Example: "AD_SET_ID_EXAMPLE"
        - Input-name (str, mandatory): Name of the ad (and of its creative).
          Example: "Publicité test - post soldes"
        - Input-access_token (str, mandatory): User access token (or the token of Marketing API >
          Tools) with the ads_management permission.
        - Input-post_id (str, optional): Existing post of the page, "<page_id>_<post_id>"; mandatory
          when the campaign objective is not OUTCOME_LEADS, refused otherwise. For OUTCOME_TRAFFIC,
          the post must contain a link to a website.
          Example: "PAGE_ID_EXAMPLE_POST_ID_EXAMPLE"
        - Input-page_id (str, optional): Page of the Lead Ads form; mandatory for OUTCOME_LEADS.
          Example: "PAGE_ID_EXAMPLE"
        - Input-lead_form_id (str, optional): ACTIVE Lead Ads form of page_id (see list_lead_forms);
          mandatory for OUTCOME_LEADS, refused otherwise.
          Example: "LEAD_FORM_ID_EXAMPLE"
        - Input-message (str, optional): Text of the Lead Ads ad; mandatory for OUTCOME_LEADS.
          Example: "Recevez notre catalogue d'automne"
        - Input-image_url (str, optional): Image (http/https URL) of the Lead Ads ad.
          Example: "https://example.com/catalogue.jpg"
        - Input-call_to_action (str, optional): Button of the Lead Ads ad. Default: "SIGN_UP".
          Choices:
              - SIGN_UP -> "S'inscrire"
              - LEARN_MORE -> "En savoir plus"
              - SUBSCRIBE -> "S'abonner"
              - GET_QUOTE -> "Obtenir un devis"
              - APPLY_NOW -> "Postuler maintenant"
        - Input-page_token (str, optional): Page access token of the page (see authenticate), used only
          to read the post (OUTCOME_TRAFFIC) or the form (OUTCOME_LEADS): the ads token cannot read
          them (Meta error #10, pages_read_engagement). Mandatory for these two objectives.

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer of the ad: {"id": "<id of the ad>"}, plus
            "creative_id": "<id of its creative>".
        Example (success):
            {
                "status": "success",
                "data": {
                    "id": "AD_ID_EXAMPLE",
                    "creative_id": "CREATIVE_ID_EXAMPLE"
                }
            }
        Errors:
            - validation: a mandatory parameter is empty, ad_account_id is not an ad account ID,
              image_url is not http/https, call_to_action is not a choice, or AD_ACCOUNT_MODE is
              no_payment (no request is sent); page_token is missing for OUTCOME_TRAFFIC or
              OUTCOME_LEADS;
              the parameters do not match the objective of the campaign (post_id missing or given,
              Lead Ads parameters missing or given), the form is not ACTIVE or not of page_id, or
              the post of an OUTCOME_TRAFFIC ad has no link to a website (found after the readings;
              nothing is created).
            - safety: the ad account has a payment method or has already spent money, or the ad set
              belongs to another account (details.problems); nothing is created.
            - api: reading the account, the ad set, the post or the form failed, or creating the
              creative or the ad failed (details.status_code, details.error; details.creative_deleted
              tells whether the creative was removed). The message ends with Meta's explanation
              (error_user_title, error_user_msg, fbtrace_id).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
        Known errors (Meta, seen during the captures):
            code 100, subcode 1815520, "Le contenu publicitaire n'utilise pas de lien valide": an
              OUTCOME_TRAFFIC ad from a post without a link to a website; now refused before
              sending (validation). Use a post with a link, or an OUTCOME_ENGAGEMENT campaign.
            code 100, subcode 1359188, "Aucun moyen de paiement": Meta refuses any ad on an account
              without a payment method; refused before sending in AD_ACCOUNT_MODE=no_payment, and
              explained in the message if it still happens (the creative is then deleted). Use a
              sandbox ad account; this project never adds a payment method.
            code 10, "(#10) This endpoint requires the 'pages_read_engagement' permission": the
              post was read with the ads token; it is now read with page_token.
            code 100, subcode 2446289, "Contenu publicitaire incomplet : La publication que vous
              avez sélectionnée pour votre publicité n'est pas disponible": the ads token
              (access_token) cannot see the post of the page. The token of the ad account must also
              have access to the page: a system user of the business, with the page and the ad
              account, is recommended.
            code 10, subcode 1341012, "Vous n'êtes pas autorisé à accéder à ce profil": same cause
              for a Lead Ads ad (the creative names the page); same solution.
            code 100, subcode 2859024, "Certification requise : Un(e) admin de l'entreprise doit
              examiner et accepter notre politique de non-discrimination": the creative is
              created, the ad is refused (the creative is then deleted). An admin of the business
              must accept Meta's non-discrimination policy once (Business settings > System
              users); nothing to change in the code.
            code 100, subcode 1487888, "Pixel de suivi requis : Votre campagne utilise un objectif
              Conversions mais n'a aucune source de suivi des conversions configurée": an
              OUTCOME_ENGAGEMENT ad set created without destination_type is handled as a
              conversions one; create_ad_set now sends destination_type=ON_POST (boost a post).
              An ad set created before this fix must be created again.
    """
    try:
        if invalid := check_required(ad_account_id=ad_account_id, ad_set_id=ad_set_id, name=name,
                                     access_token=access_token):
            return invalid
        path, invalid = account_path(ad_account_id)
        if invalid:
            return invalid
        if ads_mode() == "no_payment":
            return validation_error(NO_PAYMENT_AD, message=NO_PAYMENT_AD)
        errors = []
        if image_url is not None and not (isinstance(image_url, str)
                                          and image_url.startswith(("http://", "https://"))):
            errors.append("image_url doit être une URL http ou https.")
        if call_to_action not in CALLS_TO_ACTION:
            errors.append(f"call_to_action {call_to_action!r} inconnu (choix : {', '.join(CALLS_TO_ACTION)}).")
        if errors:
            return validation_error(errors)
        _, refused = checked_account(path, access_token)
        if refused:
            return refused
        ad_set, refused = owned_object(ad_set_id, path, access_token, "status,campaign{objective}")
        if refused:
            return refused
        objective = (ad_set.get("campaign") or {}).get("objective")
        if objective not in OPTIMIZATION_GOALS:
            return validation_error(f"objectif de la campagne {objective!r} non géré "
                                    f"(gérés : {', '.join(OPTIMIZATION_GOALS)}).")
        lead_params = {"page_id": page_id, "lead_form_id": lead_form_id, "message": message, "image_url": image_url}
        if objective == "OUTCOME_LEADS":
            missing = [key for key in ("page_id", "lead_form_id", "message", "page_token")
                       if not {**lead_params, "page_token": page_token}[key]]
            errors = (["post_id est refusé pour une campagne OUTCOME_LEADS (publicité Lead Ads : la page "
                       "et le formulaire suffisent)."] if post_id else [])
            errors += [f"{key} est obligatoire pour une campagne OUTCOME_LEADS." for key in missing]
            if errors:
                return validation_error(errors)
            form = call_graph("GET", lead_form_id, page_token, params={"fields": "status,page"},
                              error_message="Lecture du formulaire Lead Ads impossible : rien n'a été créé.",
                              throttle_retries=ADS_GET_RETRIES)
            if form["status"] != "success":
                return form
            if problems := form_usage_problems(form["data"], lead_form_id, page_id):
                return validation_error(problems)
            link_data = {"message": message, "link": LEAD_ADS_LINK,
                         "call_to_action": {"type": call_to_action, "value": {"lead_gen_form_id": lead_form_id}}}
            if image_url:
                link_data["picture"] = image_url
            creative = {"name": name, "object_story_spec": json.dumps({"page_id": page_id, "link_data": link_data})}
        else:
            given = [key for key in ("lead_form_id", "message", "image_url") if lead_params[key]]
            errors = [] if post_id else [f"post_id est obligatoire pour une campagne {objective} "
                                         "(post existant de la page)."]
            errors += [f"{key} est réservé aux campagnes OUTCOME_LEADS (objectif : {objective})." for key in given]
            if objective == LINK_OBJECTIVE and not page_token:
                errors.append("page_token est obligatoire pour une campagne OUTCOME_TRAFFIC (relecture du post "
                              "avec le token de la page).")
            if errors:
                return validation_error(errors)
            if objective == LINK_OBJECTIVE:
                post = call_graph("GET", post_id, page_token, params={"fields": POST_LINK_FIELDS},
                                  error_message="Lecture du post impossible : rien n'a été créé.",
                                  throttle_retries=ADS_GET_RETRIES)
                if post["status"] != "success":
                    return post
                if _external_link(post["data"]) is None:
                    return validation_error(
                        f"le post {post_id} ne contient pas de lien vers un site : une campagne OUTCOME_TRAFFIC "
                        "optimise les clics sur un lien (Meta refuse sinon la publicité, sous-code 1815520). "
                        "Utilise un post avec lien, ou une campagne OUTCOME_ENGAGEMENT pour booster ce post.")
            creative = {"name": name, "object_story_id": post_id}
        created = call_graph("POST", f"{path}/adcreatives", access_token, data=creative, error_message=CREATIVE_ERROR)
        if created["status"] != "success":
            return created
        creative_id = created["data"].get("id")
        if not creative_id:
            return error(CREATIVE_ERROR, {"type": "api", "response": created["data"]})
        ad = call_graph("POST", f"{path}/ads", access_token, error_message=AD_ERROR,
                        data={"name": name, "adset_id": ad_set_id,
                              "creative": json.dumps({"creative_id": creative_id}), "status": PAUSED})
        if ad["status"] == "success" and ad["data"].get("id"):
            return {**ad, "data": {**ad["data"], "creative_id": creative_id}}
        if ad["status"] == "success":
            ad = error(AD_ERROR, {"type": "api", "response": ad["data"]})
        removed = call_graph("DELETE", creative_id, access_token, error_message="Suppression du visuel impossible.")
        ad.setdefault("details", {})
        ad["details"]["creative_id"] = creative_id
        ad["details"]["creative_deleted"] = removed["status"] == "success"
        return ad
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})

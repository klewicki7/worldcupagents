"""Snapshot of common disposable / throwaway email domains (PRD F10.4).

Source: https://github.com/disposable-email-domains/disposable-email-domains (MIT).
Refresh manually: copy the latest `disposable_email_blocklist.conf` and prune to the
domains we actually see in abuse signals. Lives in code (not a migration) so we can edit
without DB churn.
"""

from __future__ import annotations

DISPOSABLE_DOMAINS: frozenset[str] = frozenset(
    {
        "10minutemail.com",
        "10minutemail.net",
        "20minutemail.com",
        "anonbox.net",
        "anonymbox.com",
        "boun.cr",
        "burnermail.io",
        "byom.de",
        "deadaddress.com",
        "discard.email",
        "discardmail.com",
        "dispostable.com",
        "dropmail.me",
        "emailondeck.com",
        "fakeinbox.com",
        "fakemail.net",
        "fakemailgenerator.com",
        "filzmail.com",
        "getairmail.com",
        "getnada.com",
        "guerrillamail.biz",
        "guerrillamail.com",
        "guerrillamail.de",
        "guerrillamail.info",
        "guerrillamail.net",
        "guerrillamail.org",
        "guerrillamailblock.com",
        "harakirimail.com",
        "incognitomail.org",
        "inboxbear.com",
        "inboxkitten.com",
        "instant-mail.de",
        "jetable.org",
        "kasmail.com",
        "mailcatch.com",
        "mailde.de",
        "maildrop.cc",
        "mailexpire.com",
        "mailforspam.com",
        "mailinator.com",
        "mailinator.net",
        "mailinator.org",
        "mailnesia.com",
        "mailnull.com",
        "mailsac.com",
        "mailtemp.info",
        "mintemail.com",
        "mohmal.com",
        "moakt.com",
        "mt2015.com",
        "mvrht.com",
        "mytemp.email",
        "nada.email",
        "nada.ltd",
        "no-spam.ws",
        "noclickemail.com",
        "nospammail.net",
        "onetimemail.com",
        "owlpic.com",
        "pokemail.net",
        "rmqkr.net",
        "sharklasers.com",
        "spam4.me",
        "spambox.us",
        "spamgourmet.com",
        "spaml.com",
        "tempail.com",
        "temp-mail.io",
        "temp-mail.org",
        "tempinbox.com",
        "tempmail.com",
        "tempmail.eu",
        "tempmail.it",
        "tempmail.us",
        "tempmailaddress.com",
        "tempmailo.com",
        "throwam.com",
        "throwawaymail.com",
        "trashmail.com",
        "trashmail.de",
        "trashmail.me",
        "trashmail.net",
        "trbvm.com",
        "wegwerfemail.de",
        "yopmail.com",
        "yopmail.fr",
        "yopmail.net",
        "zetmail.com",
    }
)


def is_disposable(email: str) -> bool:
    """Return True if the email's domain is on the disposable list. Case-insensitive."""
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1].strip().lower()
    return domain in DISPOSABLE_DOMAINS

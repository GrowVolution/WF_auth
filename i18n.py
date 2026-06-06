import json

_default = "{}"
_plural = json.dumps({
    "pf": "other"
})

_msg_keys = [
    "INVALID_USERNAME",

    "MIN_LENGTH",
    "MIN_LOWER",
    "MIN_UPPER",
    "MIN_DIGITS",
    "MIN_SPECIAL",

    "CREDENTIALS_TAKEN",
    "PRODUCTION_MODE",
    "SETUP_ALREADY_PERFORMED",
    "ROLES_NOT_ALLOWED",
    "ALREADY_LOGGED_IN",
    "INVALID_CREDENTIALS",
    "PROVIDER_ONLY",
    "NOT_LOGGED_IN",
    "ALREADY_CONNECTED",
    "INVALID_TOKEN",
    "MISSING_TOKEN",
    "INVALID_CSRF",
    "MISSING_CSRF",
    "CSRF_MISMATCH",
    "UNKNOWN_USER",
    "ALREADY_CONFIRMED",
    "NO_HANDLER",
    "USERNAME_TAKEN",
    "UNKNOWN_ERROR",
    "The part after the @-sign is not valid. It should have a period.",
    "UNKNOWN_EMAIL",
    "Too many requests",
    "MISSING_CURRENT_PASSWORD",
    "EMAIL_TAKEN",
    "NOT_AUTHORIZED",
    "NOT_AUTHENTICATED",
    "NO_EMAIL",

]

translations = lambda: {
    "en": {
        _msg_keys[0]: {
            _default: "Invalid username"
        },

        _msg_keys[1]: {
            _default: "Password must be at least %(num)i character long.",
            _plural: "Password must be at least %(num)i characters long."
        },
        _msg_keys[2]: {
            _default: "Password must contain at least %(num)i lowercase letter.",
            _plural: "Password must contain at least %(num)i lowercase letters."
        },
        _msg_keys[3]: {
            _default: "Password must contain at least %(num)i uppercase letter.",
            _plural: "Password must contain at least %(num)i uppercase letters."
        },
        _msg_keys[4]: {
            _default: "Password must contain at least %(num)i digit.",
            _plural: "Password must contain at least %(num)i digits."
        },
        _msg_keys[5]: {
            _default: "Password must contain at least %(num)i special character.",
            _plural: "Password must contain at least %(num)i special characters."
        },

        _msg_keys[6]: {
            _default: "Username or email already taken"
        },
        _msg_keys[7]: {
            _default: "Not allowed in production mode"
        },
        _msg_keys[8]: {
            _default: "Initial setup already performed"
        },
        _msg_keys[9]: {
            _default: "Roles are not allowed for default registration"
        },
        _msg_keys[10]: {
            _default: "Already logged in"
        },
        _msg_keys[11]: {
            _default: "Invalid credentials"
        },
        _msg_keys[12]: {
            _default: "Must login with provider"
        },
        _msg_keys[13]: {
            _default: "Not logged in"
        },
        _msg_keys[14]: {
            _default: "Provider '%(provider)s' already connected"
        },
        _msg_keys[15]: {
            _default: "Invalid token"
        },
        _msg_keys[16]: {
            _default: "Missing token"
        },
        _msg_keys[17]: {
            _default: "Invalid CSRF token"
        },
        _msg_keys[18]: {
            _default: "Missing CSRF token"
        },
        _msg_keys[19]: {
            _default: "CSRF token mismatch"
        },
        _msg_keys[20]: {
            _default: "Unknown user"
        },
        _msg_keys[21]: {
            _default: "Already confirmed"
        },
        _msg_keys[22]: {
            _default: "No handler function registered"
        },
        _msg_keys[23]: {
            _default: "Username already taken"
        },
        _msg_keys[24]: {
            _default: "Unknown error"
        },
        _msg_keys[26]: {
            _default: "Unknown email address"
        },
        _msg_keys[28]: {
            _default: "Missing current password"
        },
        _msg_keys[29]: {
            _default: "Email already taken"
        },
        _msg_keys[30]: {
            _default: "Not authorized"
        },
        _msg_keys[31]: {
            _default: "Not authenticated"
        },
        _msg_keys[32]: {
            _default: "User has no email"
        },

    },

    "de": {
        _msg_keys[0]: {
            _default: "Ungültiger Benutzername"
        },

        _msg_keys[1]: {
            _default: "Das Passwort muss mindestens %(num)i Zeichen lang sein.",
            _plural: "Das Passwort muss mindestens %(num)i Zeichen lang sein."
        },
        _msg_keys[2]: {
            _default: "Das Passwort muss mindestens %(num)i Kleinbuchstabe enthalten.",
            _plural: "Das Passwort muss mindestens %(num)i Kleinbuchstaben enthalten."
        },
        _msg_keys[3]: {
            _default: "Das Passwort muss mindestens %(num)i Großbuchstabe enthalten.",
            _plural: "Das Passwort muss mindestens %(num)i Großbuchstaben enthalten."
        },
        _msg_keys[4]: {
            _default: "Das Passwort muss mindestens %(num)i Ziffer enthalten.",
            _plural: "Das Passwort muss mindestens %(num)i Ziffern enthalten."
        },
        _msg_keys[5]: {
            _default: "Das Passwort muss mindestens %(num)i Sonderzeichen enthalten.",
            _plural: "Das Passwort muss mindestens %(num)i Sonderzeichen enthalten."
        },

        _msg_keys[6]: {
            _default: "Benutzername oder E-Mail-Adresse bereits vergeben"
        },
        _msg_keys[7]: {
            _default: "Nicht erlaubt im Produktivbetrieb"
        },
        _msg_keys[8]: {
            _default: "Initiale Einrichtung bereits abgeschlossen"
        },
        _msg_keys[9]: {
            _default: "Rollen dürfen in der Standardregistrierung nicht verwendet werden"
        },
        _msg_keys[10]: {
            _default: "Bereits eingeloggt"
        },
        _msg_keys[11]: {
            _default: "Falsche Anmeldedaten"
        },
        _msg_keys[12]: {
            _default: "Login nur über Provider möglich"
        },
        _msg_keys[13]: {
            _default: "Nicht eingeloggt"
        },
        _msg_keys[14]: {
            _default: "Anbieter '%(provider)s' bereits verbunden"
        },
        _msg_keys[15]: {
            _default: "Ungültiger Token"
        },
        _msg_keys[16]: {
            _default: "Token fehlt"
        },
        _msg_keys[17]: {
            _default: "Ungültiger CSRF-Token"
        },
        _msg_keys[18]: {
            _default: "CSRF-Token fehlt"
        },
        _msg_keys[19]: {
            _default: "Keine CSRF-Übereinstimmung"
        },
        _msg_keys[20]: {
            _default: "Unbekannter Benutzer"
        },
        _msg_keys[21]: {
            _default: "Bereits bestätigt"
        },
        _msg_keys[22]: {
            _default: "Keine Verarbeitungsfunktion registriert"
        },
        _msg_keys[23]: {
            _default: "Benutzername bereits vergeben"
        },
        _msg_keys[24]: {
            _default: "Unbekannter Fehler"
        },
        _msg_keys[25]: {
            _default: "Der Abschnitt nach dem @ ist ungültig. Er sollte einen Punkt enthalten."
        },
        _msg_keys[26]: {
            _default: "Unbekannte E-Mail-Adresse"
        },
        _msg_keys[27]: {
            _default: "Zu viele Anfragen"
        },
        _msg_keys[28]: {
            _default: "Aktuelles Passwort fehlt"
        },
        _msg_keys[29]: {
            _default: "E-Mail-Adresse bereits vergeben"
        },
        _msg_keys[30]: {
            _default: "Nicht autorisiert"
        },
        _msg_keys[31]: {
            _default: "Nicht authentifiziert"
        },
        _msg_keys[32]: {
            _default: "Benutzer hat keine E-Mail-Adresse"
        }

    }
}


_msg_keys = [
    "INVALID_USERNAME",

    "MIN_PSW_LEN",
    "MIN_LOWER",
    "MIN_UPPER",
    "MIN_DIGITS",
    "MIN_SPECIAL",

    "Username or email already taken",
    "Not allowed in production",
    "Initial setup already performed",
    "Roles are not allowed for default registration",
    "Already logged in",
    "Invalid credentials",
    "Must login with provider",
    "Not logged in",
    "Already connected",
    "Invalid token",
    "Missing token",
    "Invalid CSRF token",
    "Missing CSRF token",
    "CSRF mismatch",
    "Unknown user",
    "Already confirmed",
    "No confirmation handler",
    "Username already taken",
    "Unknown error",
    "The part after the @-sign is not valid. It should have a period.",
    "Unknown email",
    "No reset handler",
    "Too many requests",

]

translations = {
    "en": {
        _msg_keys[0]: {
            ("one",): "Invalid username"
        },

        _msg_keys[1]: {
            ("one",): "Password must be at least %(len)i characters long."
        },
        _msg_keys[2]: {
            ("one",): "Password must contain at least %(num)i lowercase letter.",
            ("other",): "Password must contain at least %(num)i lowercase letters."
        },
        _msg_keys[3]: {
            ("one",): "Password must contain at least %(num)i uppercase letter.",
            ("other",): "Password must contain at least %(num)i uppercase letters."
        },
        _msg_keys[4]: {
            ("one",): "Password must contain at least %(num)i digit.",
            ("other",): "Password must contain at least %(num)i digits."
        },
        _msg_keys[5]: {
            ("one",): "Password must contain at least %(num)i special character.",
            ("other",): "Password must contain at least %(num)i special characters."
        },

    },

    "de": {
        _msg_keys[0]: {
            ("one",): "Ungültiger Benutzername"
        },

        _msg_keys[1]: {
            ("one",): "Das Passwort muss mindestens %(len)i Zeichen lang sein."
        },
        _msg_keys[2]: {
            ("one",): "Das Passwort muss mindestens %(num)i Kleinbuchstabe enthalten.",
            ("other",): "Das Passwort muss mindestens %(num)i Kleinbuchstaben enthalten."
        },
        _msg_keys[3]: {
            ("one",): "Das Passwort muss mindestens %(num)i Großbuchstabe enthalten.",
            ("other",): "Das Passwort muss mindestens %(num)i Großbuchstaben enthalten."
        },
        _msg_keys[4]: {
            ("one",): "Das Passwort muss mindestens %(num)i Ziffer enthalten.",
            ("other",): "Das Passwort muss mindestens %(num)i Ziffern enthalten."
        },
        _msg_keys[5]: {
            ("one",): "Das Passwort muss mindestens %(num)i Sonderzeichen enthalten.",
            ("other",): "Das Passwort muss mindestens %(num)i Sonderzeichen enthalten."
        },

        _msg_keys[6]: {
            ("one",): "Benutzername oder E-Mail-Adresse bereits vergeben"
        },
        _msg_keys[7]: {
            ("one",): "Nicht erlaubt im Produktivbetrieb"
        },
        _msg_keys[8]: {
            ("one",): "Initiale Einrichtung bereits abgeschlossen"
        },
        _msg_keys[9]: {
            ("one",): "Rollen dürfen in der Standardregistrierung nicht verwendet werden"
        },
        _msg_keys[10]: {
            ("one",): "Bereits eingeloggt"
        },
        _msg_keys[11]: {
            ("one",): "Falsche Anmeldedaten"
        },
        _msg_keys[12]: {
            ("one",): "Login nur über Provider möglich"
        },
        _msg_keys[13]: {
            ("one",): "Nicht eingeloggt"
        },
        _msg_keys[14]: {
            ("one",): "Bereits verbunden"
        },
        _msg_keys[15]: {
            ("one",): "Ungültiger Token"
        },
        _msg_keys[16]: {
            ("one",): "Token fehlt"
        },
        _msg_keys[17]: {
            ("one",): "Ungültiger CSRF-Token"
        },
        _msg_keys[18]: {
            ("one",): "CSRF-Token fehlt"
        },
        _msg_keys[19]: {
            ("one",): "Keine CSRF-Übereinstimmung"
        },
        _msg_keys[20]: {
            ("one",): "Unbekannter Benutzer"
        },
        _msg_keys[21]: {
            ("one",): "Bereits bestätigt"
        },
        _msg_keys[22]: {
            ("one",): "Bestätigungsfunktion fehlt"
        },
        _msg_keys[23]: {
            ("one",): "Benutzername bereits vergeben"
        },
        _msg_keys[24]: {
            ("one",): "Unbekannter Fehler"
        },
        _msg_keys[25]: {
            ("one",): "Der Abschnitt nach dem @ ist ungültig. Er sollte einen Punkt enthalten."
        },
        _msg_keys[26]: {
            ("one",): "Unbekannte E-Mail-Adresse"
        },
        _msg_keys[27]: {
            ("one",): "Funktion zum Zurücksetzen fehlt"
        },
        _msg_keys[28]: {
            ("one",): "Zu viele Anfragen"
        },

    }
}

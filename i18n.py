
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
    "Missing CSRF token",
    "CSRF mismatch",

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

        _msg_keys[6]: {
            ("one",): "Confirm your email address"
        },
        _msg_keys[7]: {
            ("one",): "Welcome %(user)s!\n\n"
                      "To verify it's you, please confirm your email address by clicking the link below:\n\n"
                      "%(link)s\n\n"
                      "If you did not create an account, please ignore this email."
        },
        _msg_keys[8]: {
            ("one",): "Hey %(user)s!<br><br>"
                      "To verify it's you, please confirm your email address by clicking the button below:"
        },
        _msg_keys[9]: {
            ("one",): "If the button does not work, you can also confirm your email address using the link below:<br><br>"
                      "<a href='%(link)s'>%(link)s</a><br><br>"
                      "If you did not create an account, please ignore this email."
        },
        _msg_keys[10]: {
            ("one",): "Hey %(user)s!\n\n"
                      "To change your email address, we need to confirm this one by clicking the link below:\n\n"
                      "%(link)s\n\n"
                      "If you did not request to change your email address, please ignore this email."
        },
        _msg_keys[11]: {
            ("one",): "Hey %(user)s!<br><br>"
                      "To change your email address, we need to confirm this one by clicking the button below:"
        },
        _msg_keys[12]: {
            ("one",): "If the button does not work, you can also change your email address using the link below:<br><br>"
                      "<a href='%(link)s'>%(link)s</a><br><br>"
                      "If you did not request to change your email address, please ignore this email."
        },
        _msg_keys[13]: {
            ("one",): "Confirm"
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
            ("one",): "Bestätige deine E-Mail-Adresse"
        },
        _msg_keys[7]: {
            ("one",): "Willkommen %(user)s!\n\n"
                      "Um sicherzustellen, dass du es bist, bestätige bitte deine E-Mail-Adresse, indem du auf den Link unten klickst:\n\n"
                      "%(link)s\n\n"
                      "Wenn du kein Konto angelegt hast, kannst du diese E-Mail ignorieren."
        },
        _msg_keys[8]: {
            ("one",): "Willkommen %(user)s!<br><br>"
                      "Um sicherzustellen, dass du es bist, bestätige bitte deine E-Mail-Adresse, indem du auf folgenden Button klickst:"
        },
        _msg_keys[9]: {
            ("one",): "Falls der Button nicht funktioniert, kannst du deine E-Mail-Adresse auch über den Link unten bestätigen:<br><br>"
                      "<a href='%(link)s'>%(link)s</a><br><br>"
                      "Wenn du kein Konto angelegt hast, kannst du diese E-Mail ignorieren."
        },
        _msg_keys[10]: {
            ("one",): "Hey %(user)s!\n\n"
                      "Um deine E-Mail-Adresse zu ändern, musst du diese hier kurz bestätigen, indem du auf den Link unten klickst:\n\n"
                      "%(link)s\n\n"
                      "Wenn diese Anfrage nicht von dir kommt, kannst du diese E-Mail ignorieren."
        },
        _msg_keys[11]: {
            ("one",): "Hey %(user)s!<br><br>"
                      "Um deine E-Mail-Adresse zu ändern, musst du diese hier kurz bestätigen, indem du auf folgenden Button klickst:"
        },
        _msg_keys[12]: {
            ("one",): "Falls der Button nicht funktioniert, kannst du deine E-Mail-Adresse auch über den Link unten bestätigen:<br><br>"
                      "<a href='%(link)s'>%(link)s</a><br><br>"
                      "Wenn diese Anfrage nicht von dir kommt, kannst du diese E-Mail ignorieren."
        },
        _msg_keys[13]: {
            ("one",): "Bestätigen"
        },

        _msg_keys[14]: {
            ("one",): "Benutzername oder E-Mail-Adresse bereits vergeben"
        },
        _msg_keys[15]: {
            ("one",): "Nicht erlaubt im Produktivbetrieb"
        },
        _msg_keys[16]: {
            ("one",): "Initiale Einrichtung bereits abgeschlossen"
        },
        _msg_keys[17]: {
            ("one",): "Rollen dürfen in der Standardregistrierung nicht verwendet werden"
        },
        _msg_keys[18]: {
            ("one",): "Bereits eingeloggt"
        },
        _msg_keys[19]: {
            ("one",): "Falsche Anmeldedaten"
        },
        _msg_keys[20]: {
            ("one",): "Login nur über Provider möglich"
        },
        _msg_keys[21]: {
            ("one",): "Nicht eingeloggt"
        },
        _msg_keys[22]: {
            ("one",): "Bereits verbunden"
        },
        _msg_keys[23]: {
            ("one",): "Ungültiger Token"
        },
        _msg_keys[24]: {
            ("one",): "CSRF-Token fehlt"
        },
        _msg_keys[25]: {
            ("one",): "Keine CSRF-Übereinstimmung"
        },

    }
}

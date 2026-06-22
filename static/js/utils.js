export function getCookie(name) {
    const cookies = document.cookie.split("; ")

    for (let cookie of cookies) {
        const [key, value] = cookie.split("=")
        if (key === name) {
            return decodeURIComponent(value)
        }
    }

    return null
}

export function csrfFetch(input, init = {}) {
    const headers = new Headers(init.headers)
    headers.set("X-CSRF-Token", getCookie("csrf_token") || "")

    return fetch(input, {
        credentials: "include",
        ...init,
        headers
    })
}

csrfFetch("/auth/api/v1/users/login/available", {
    method: "POST"
}).then(r => {
    if (!r.ok && localStorage.getItem("auth.logged_in") !== "0") {
        fetch("/auth/api/v1/users/logout",{
            credentials: "include"
        }).catch(() => null)
        setTimeout(() => {
            if (window.location.href !== "/")
                window.location.href = "/"
            else
                window.location.reload()
        }, 1500)
        localStorage.setItem("auth.logged_in", "0")
    } else if (r.ok) {
        localStorage.setItem("auth.logged_in", "1")
    }
}).catch(() => null)

window.wf.adt.auth = {
    getCookie,
    csrfFetch
}
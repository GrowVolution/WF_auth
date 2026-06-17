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
    if (!r.ok) {
        fetch("/auth/api/v1/users/logout",{
            credentials: "include"
        }).then(r => r.json()).catch(() => null)
        window.location.reload()
    }
})

window.wf.adt.auth = {
    getCookie,
    csrfFetch
}
import router from '../router.js'
import useAuthStore from '../auth.js'

export default {
    template: /*html*/ `

        <v-breadcrumbs :items="items"></v-breadcrumbs>

        <p>Token: {{ authStore.token_info }}</p>
        <p>Data: {{ authStore.decoded_token() }}</p>
        <p>User: {{ user }}</p>

        <v-btn color="primary" @click="logout">Logout</v-btn>

    `,
    data() {
        return {
            user: null,
            items: [
                {title: "Home", to: {name: "home"}},
                {title: "Profile", to: {name: "profile"}},
            ]
        };
    },
    setup() {
        return {
            authStore: useAuthStore(),
        };
    },
    async mounted() {
        const authStore = useAuthStore();
        document.title = "Profile";
        this.user = await authStore.authenticated_request({path: "/auth/me"});
    },
    methods: {
        logout() {
            const authStore = useAuthStore();
            authStore.logout();
            router.push({ name: "home" });
        }
    },
}

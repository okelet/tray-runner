import Config from '../config.js'
import router from '../router.js'
import useAuthStore from '../auth.js'

export default {
    template: /*html*/`

        <v-breadcrumbs :items="breadcrumbItems"></v-breadcrumbs>

        <v-card class="mx-auto px-6 py-8" max-width="344">

        <v-alert type="error" v-model="loginError">{{ loginError }}</v-alert>

        <v-form ref="form" v-model="form" @submit.prevent="login">

            <v-text-field ref="token_code" v-model="token_code" type="password" label="Login token"></v-text-field>

            <v-btn :disabled="!form" :loading="loading" color="primary" type="submit">Validate</v-btn>

        </v-form>


    </v-card>

    `,
    data() {
        return {
            config: Config,
            loginError: null,
            token_code: "",
            form: false,
            loading: false,
            breadcrumbItems: [
                { title: "Home", to: { name: "home" } },
                { title: "Login", to: { name: "login" } },
            ]
        };
    },
    validations: {
        token_code: {
            required: VuelidateValidators.required,
        },
    },
    setup() {
        return {
            v$: Vuelidate.useVuelidate(),
        };
    },
    created() {
        // Redirect from this login view if the user is already logged in
        const authStore = useAuthStore();
        if (authStore.token_info) {
            router.push(this.$route.query.returnUrl || { name: "home" });
        }
    },
    mounted() {
        document.title = "Login";
        this.$refs.token_code.$el.focus()
        const query_token = this.$route.query.token;
        if (query_token) {
            this.token_code = query_token;
            this.login();
        }
    },
    methods: {
        async login() {
            if (!this.form) return;
            /*
            const isFormCorrect = await this.v$.$validate()
            if (!isFormCorrect) return;
            */
            const toast = this.$toast.info("Logging in...")
            this.loading = true;
            this.loginError = null;
            const authStore = useAuthStore();
            const loginError = await authStore.login(this.token_code);
            this.loading = false;
            toast.dismiss();
            if (loginError) {
                this.loginError = loginError;
            }
            else {
                if (this.$route.query.returnUrl) {
                    router.push(this.$route.query.returnUrl);
                }
                else {
                    router.push({ name: "home" });
                }
            }
        },
    },
}

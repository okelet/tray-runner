import useAuthStore from './auth.js'
import router from './router.js'

const app = Vue.createApp({
    template: /*html*/`
        <v-app>

            <v-app-bar>

                <v-app-bar-nav-icon variant="text" @click.stop="drawer = !drawer"></v-app-bar-nav-icon>
                <v-app-bar-title>VueJS Cognito demo</v-app-bar-title>
                <v-spacer></v-spacer>

                <v-btn icon><v-icon>mdi-magnify</v-icon></v-btn>
                <v-btn icon><v-icon>mdi-heart</v-icon></v-btn>

            </v-app-bar>

            <v-main>

                <v-navigation-drawer v-model="drawer">
                    <v-list :items="drawerItems"></v-list>
                </v-navigation-drawer>

                <v-container fluid>
                    <router-view></router-view>
                </v-container>

            </v-main>

            <v-footer app>
                <!-- -->
            </v-footer>

        </v-app>
    `,
    data() {
        return {
            // message: 'Hello Vue!',
            drawer: null,
            drawerItems: [
                {
                    title: "Home",
                    props: {
                        to: { name: "home" },
                        "prepend-icon": "mdi-home",
                    },
                },
                {
                    title: "Login",
                    props: {
                        to: { name: "login" },
                        "prepend-icon": "mdi-account-arrow-left",
                    },
                },
                {
                    title: "Commands",
                    props: {
                        to: { name: "commands_list" },
                        "prepend-icon": "mdi-account",
                    },
                },
                {
                    title: "Profile",
                    props: {
                        to: { name: "profile" },
                        "prepend-icon": "mdi-account",
                    },
                },
                {
                    title: "About",
                    props: {
                        to: { name: "about" },
                        "prepend-icon": "mdi-information",
                    },
                },
            ],
        }
    },
    components: {
        // MyComponent,
    },
    setup() {
        return {
            authStore: useAuthStore(),
        };
    },
    mounted() {
    }
});

app.use(router)
app.use(Vuetify.createVuetify({}))
app.use(Pinia.createPinia({}))
app.use(VueToast.ToastPlugin, { position: 'top-right' });
app.mount("#app");

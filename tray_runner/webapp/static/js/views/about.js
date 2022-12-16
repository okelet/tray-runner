import useAuthStore from '../auth.js'

export default {
    template: /*html*/ `
        <v-breadcrumbs :items="items"></v-breadcrumbs>
    `,
    data() {
        return {
            items: [
                {title: "Home", to: {name: "home"}},
                {title: "About", to: {name: "about"}},
            ]
        };
    },
    setup() {
        return {
            authStore: useAuthStore(),
        };
    },
    mounted() {
        document.title = "About";
    },
}

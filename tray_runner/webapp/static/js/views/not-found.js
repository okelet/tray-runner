export default {
    template: /*html*/ `
        <v-breadcrumbs :items="items"></v-breadcrumbs>
    `,
    data() {
        return {
            items: [
                {title: "Home", to: {name: "home"}},
                {title: "404"},
            ]
        };
    },
    mounted() {
        document.title = "404 - Not found";
    },
}

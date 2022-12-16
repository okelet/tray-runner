export default {
    template: /*html*/ `
        <v-breadcrumbs :items="items"></v-breadcrumbs>
    `,
    data() {
        return {
            items: [
                {title: "Home", to: {name: "home"}},
            ]
        };
    },
    mounted() {
        document.title = "Home";
    },
}

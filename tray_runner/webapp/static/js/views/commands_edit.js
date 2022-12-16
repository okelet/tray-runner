import router from '../router.js'
import useAuthStore from '../auth.js'

export default {
    template: /*html*/ `

        <v-breadcrumbs :items="items"></v-breadcrumbs>

        <p>Command</p>

        <pre>{{ command }}</pre>

    `,
    data() {
        return {
            command: null,
            items: [
                {title: "Home", to: {name: "home"}},
                {title: "Commands", to: {name: "commands_list"}},
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
        const command_id = this.$route.params.id;
        try {
            this.command = await authStore.authenticated_request({path: `/commands/${command_id}`});
            document.title = `Commands - ${this.command.name}`;
            this.items.push({title: this.command.name, to: {name: "commands_show", params: {id: this.command.id}}})
            this.items.push({title: "Edit", to: {name: "commands_edit", params: {id: this.command.id}}})
        }
        catch (error) {
            this.$toast.error(`Error loading command: ${error}.`);
            router.push({name: "commands_list"});
        }
    },
    methods: {
    },
}

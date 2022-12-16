import router from '../router.js'
import useAuthStore from '../auth.js'

export default {
    template: /*html*/ `

        <v-breadcrumbs :items="items"></v-breadcrumbs>

        <p>Number of commands : {{ commands.length }}</p>

        <ul v-if="commands" v-for="(command, index) in commands" :key="command.id">
            <li><router-link :to="{ name: 'commands_show', params: { id: command.id }}">{{ command.name }}</router-link> - <router-link :to="{ name: 'commands_edit', params: { id: command.id }}">Edit</router-link> | <button @click="delete_command(command.id)">Delete</button></li>
        </ul>

    `,
    data() {
        return {
            commands: [],
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
        document.title = "Commands";
        this.refresh_commands();
    },
    methods: {
        async refresh_commands() {
            const authStore = useAuthStore();
            try {
                this.commands = await authStore.authenticated_request({path: "/commands"});
            }
            catch (error) {
                this.$toast.error(`Error loading the list of commands: ${error}.`);
            }
        },
        async delete_command(command_id) {
            const authStore = useAuthStore();
            try {
                await authStore.authenticated_request({path: `/commands/${command_id}`, method: "delete"});
                this.$toast.success(`Command deleted.`);
                this.refresh_commands();
            }
            catch (error) {
                this.$toast.error(`Error deleting the command: ${error}.`);
            }
        },
    },
}

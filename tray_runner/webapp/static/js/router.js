import Config from './config.js'
import useAuthStore from './auth.js'

import NotFound from './views/not-found.js'
import Home from './views/home.js'
import CommandsList from './views/commands_list.js'
import CommandsShow from './views/commands_show.js'
import CommandsEdit from './views/commands_edit.js'
import Login from './views/login.js'
import Profile from './views/profile.js'
import About from './views/about.js'

const router = VueRouter.createRouter({
    history: VueRouter.createWebHashHistory(),
    routes: [
        { path: '/:pathMatch(.*)*', component: NotFound, },
        { path: '/', name: "home", component: Home, },
        { path: '/login', name: "login", component: Login, },
        { path: '/profile', name: "profile", component: Profile, meta: { requiresAuth: true }, },
        { path: '/commands', name: "commands_list", component: CommandsList, meta: { requiresAuth: true }, },
        { path: '/commands/show/:id', name: "commands_show", component: CommandsShow, meta: { requiresAuth: true }, },
        { path: '/commands/edit/:id', name: "commands_edit", component: CommandsEdit, meta: { requiresAuth: true }, },
        { path: '/about', name: "about", component: About, },
    ],
});

router.beforeResolve(async (to, from, next) => {
    const auth = useAuthStore();
    if (to.matched.some(record => record.meta.requiresAuth)) {
        if (auth.token_info) {
            next();
        }
        else {
            next({
                name: "login",
                query: {
                    returnUrl: to.fullPath
                }
            });
        }
    }
    else {
        next();
    }
});

export default router;

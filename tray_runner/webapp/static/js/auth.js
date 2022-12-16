import Config from './config.js'
const baseApiUrl = Config.BASE_API_URL;

const useAuthStore = Pinia.defineStore({
    id: 'auth',
    state: () => ({
        token_info: JSON.parse(localStorage.getItem('token_info')),
    }),
    actions: {
        async login(token_code) {
            try {
                const resp = await axios.post(
                    `${baseApiUrl}/auth/login`,
                    { token: token_code },
                );
                if (resp.data && resp.data.access_token) {
                    this.update_local_token(resp.data.access_token);
                    return null;
                }
                else {
                    return "Missing access token in response"
                }
            } catch (error) {
                if (error.response.data && error.response.data.detail) {
                    return error.response.data.detail;
                }
                else {
                    return error.message;
                }
            }
        },
        update_local_token(access_token) {
            this.token_info = access_token;
            localStorage.setItem('token_info', JSON.stringify(this.token_info))
        },
        remove_local_token() {
            this.token_info = null;
            localStorage.removeItem('token_info');
        },
        logout() {
            this.remove_local_token();
        },
        decoded_token() {
            if (this.token_info) {
                return jwt_decode(this.token_info);
            }
            else {
                return null;
            }
        },
        async authenticated_request({path, method, params, data, timeout, responseType}) {
            method = method || "get";
            params = params || {};
            data = data || {};
            timeout = timeout || 3000;
            responseType = responseType || "json";
            if (this.token_info) {
                const headers = {
                    "Authorization": `Bearer ${this.token_info}`,
                };
                while(true) {
                    try {
                        const resp = await axios.request({
                            method: method,
                            url: `${baseApiUrl}${path}`,
                            params: params,
                            data: data,
                            headers: headers,
                            timeout: timeout,
                            responseType: responseType,
                        });
                        // .then(console.log)
                        // .catch(console.log);
                        // TODO: Error and token refresh management
                        return resp.data;
                    }
                    catch (error) {
                        console.log("Error requesting " + path);
                        console.log(error);
                        if (error.response && error.response.status === 401) {
                            // Unauthorized, invalid credentials
                            // Refresh token
                            try {
                                const refresh_token = await axios.request({
                                    method: "get",
                                    url: `${baseApiUrl}/auth/refresh`,
                                    headers: {
                                        "Authorization": `Bearer ${this.token_info}`,
                                    }
                                });
                            }
                            catch (error) {
                                console.log("Error refreshing token");
                                console.log(error);
                            }
                            throw "Need to refresh token."
                        }
                        else if (error.response && error.response.data && error.response.data.detail) {
                            throw error.response.data.detail;
                        }
                        else if (error.message) {
                            throw error.message;
                        }
                        else {
                            throw error;
                        }
                    }
                }
            }
            else {
                throw "Trying to perform an authenticated request when the user is not logged in yet.";
            }
        }
    }
});

export default useAuthStore;

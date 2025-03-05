Vue.component(
    'Sample',
    {
        props: {

        },
        delimiters: ['[[', ']]'],
        methods: {
            account_edited(data) {
                console.log(data)
            },
            click(){
                //this.$refs.form.validate();
            }
        },
        template: `
            <div class="w-100">
                <button @click="click">test</button>
                <auth-fields-form
                    ref="form"
                    @on_edit="account_edited"
                ></auth-fields-form>
            </div>
        `
    }
);

Vue.component(
    'convert-cur-block',
    {
        delimiters: ['[[', ']]'],
        props: {
            items: {
                type: Array,
                default() {
                    return [
                        {
                            id: 'rubusdt',
                            give: 'RUB',
                            get: 'USDT',
                            value: null
                        },
                        {
                            id: 'usdtcny',
                            give: 'USDT',
                            get: 'CNY',
                            value: null
                        }
                    ]
                }
            }
        },
        model: {
            prop: 'items',
            event: 'changed'
        },
        data(){
            return {
                rates: {}
            }
        },
        mounted(){
        },
        methods: {
            item(id) {
                for (let i=0; i<this.items.length; i++){
                    const item = this.items[i];
                    if (item.id === id) {
                        return item;
                    }
                }
                return null;
            },
            on_changed(id) {
                const i = this.item(id);
                this.$emit('changed', i);
            }
        },
        template: `
            <div class="w-100">
                <div class="row p-1" v-for="item in items">
                    <div class="col-1">
                        <span class="text-secondary">
                            отдаю
                        </span>
                    </div>
                    <div class="col-2">
                        <input class="form-control form-control-sm bg-secondary text-light"
                            type="text"
                            v-model="item.give"
                            @input="on_changed(item.id)"
                        >
                    </div>
                    <div class="col-1">
                        &rarr;
                    </div>
                    <div class="col-2">
                        <input class="form-control form-control-sm"
                            type="number"
                            v-model="item.value"
                            placeholder="Курс"
                            @input="on_changed(item.id)"
                        >
                    </div>
                    <div class="col-1">
                        &rarr;
                    </div>
                    <div class="col-1">
                        <span class="text-secondary">
                            получаю
                        </span>
                    </div>
                    <div class="col-2">
                        <input class="form-control form-control-sm bg-secondary text-light"
                            type="text"
                            v-model="item.get"
                            @input="on_changed(item.id)"
                        >
                    </div>
                </div>
            </div>
        `
    }
);

Vue.component(
    'create-order',
    {
        delimiters: ['[[', ']]'],
        emits: ['on_success', 'on_error'],
        data(){
            return {
                select: null,  // payment-request, simple,
                payment_request: {
                    customer: '',
                    description: '',
                    error: null,
                    src: {
                        currency: 'RUB',
                        amount: null
                    },
                    destination: {
                        currency: 'CNY',
                        amount: null
                    },
                    private: {
                        token: 'USDT',
                        source: 'Garantex',
                        amount: null
                    }
                },
                loading: false,
                error_msg: null
            }
        },
        methods: {
            validate(){
                if (this.select === 'payment-request') {
                    // inputs
                    const customer = this.$refs.pr_customer;
                    const description = this.$refs.pr_description;
                    const src_amount = this.$refs.pr_src_amount;
                    const src_currency = this.$refs.pr_src_currency;
                    const dest_amount = this.$refs.pr_dest_amount;
                    const dest_currency = this.$refs.pr_dest_currency;

                    const inputs = [customer, description, src_amount, src_currency];
                    // clear
                    for (let i=0; i<inputs.length; i++) {
                        let el = inputs[i];
                        el.setCustomValidity('');
                    }
                    // checks
                    for (let i=0; i<inputs.length; i++) {
                        let el = inputs[i];
                        if (!el.value){
                            el.setCustomValidity("Обязателен для заполнения");
                            el.reportValidity();
                            return false
                        }
                    }
                    //
                    return true
                }
                //
                return false
            },
            on_pr_cur_converter_change(){
                const comp = this.$refs.pr_cur_converter;
                this.payment_request.src.currency = comp.items[0].give;
                this.payment_request.destination.currency = comp.items[comp.items.length-1].get;
                this.on_pr_src_amount();
            },
            get_pr_ratios(print_error = true){
                const comp = this.$refs.pr_cur_converter;
                const ratio1 = comp.items[0].value;
                const ratio2 = comp.items[comp.items.length-1].value;
                this.payment_request.error = null;
                if (ratio1 && ratio2) {
                    return [ratio1, ratio2]
                }
                else {
                    if (print_error) {
                        this.payment_request.error = 'задайте курсы'
                    }
                }
            },
            on_pr_amount(path='direct'){
                const ratios = this.get_pr_ratios();
                if (!ratios) {
                    return
                }
                const ratio1 = ratios[0];
                const ratio2 = ratios[1];
                if (ratio1 && ratio2) {
                    if (path === 'direct') {
                        const el = this.$refs.pr_src_amount;
                        if (el.value) {
                            const rate = 1 / ratio1 * ratio2;
                            const amount = this.payment_request.src.amount * rate;
                            this.payment_request.destination.amount = amount.toFixed(2);
                        } else {
                            this.payment_request.error = 'задайте сумму'
                        }
                    }
                    else if (path === 'revert') {
                        const el = this.$refs.pr_dest_amount;
                        if (el.value) {
                            const rate = 1 / ratio1 * ratio2;
                            const amount = this.payment_request.destination.amount / rate;
                            this.payment_request.src.amount = amount.toFixed(2);
                        } else {
                            this.payment_request.error = 'задайте сумму'
                        }
                    }
                }
            },
            submit(){
                let success = this.validate();
                if (success) {
                    const self = this;
                    self.error_msg = null;
                    self.loading = true;
                    const amount = parseFloat(this.payment_request.src.amount);
                    axios
                       .post(
                           '/api/orders',
                           JSON.stringify(
                               {
                                  type: 'payment-request',
                                  payment_request: {
                                      description: this.payment_request.description,
                                      customer: this.payment_request.customer,
                                      amount: amount,
                                      currency: this.payment_request.src.currency,
                                      details: {
                                          payment_ttl: 15*60  //15 min
                                      }
                                  }
                               }
                           ),
                           {
                                headers: {'Content-Type': 'application/json'}
                           }
                       )
                       .then(
                           (response) => {
                               // console.log(response.data);
                               self.$emit('on_success')
                           }
                       ).catch(
                          (e) => {
                               const err = gently_extract_error_msg(e);
                               self.error_msg = err;
                               self.$emit('on_error', err);
                          }
                       ).finally(
                          ()=>{
                               self.loading = false;
                          }
                       )
                }
            }
        },
        template: `
            <div class="w-100">
                <button 
                    v-if="select != null"
                    class="btn btn-sm btn-primary"
                    style="float:left;"
                    @click.prevent="select = null"
                >
                    &larr; назад
                </button>
                
                <div v-if="!select" class="row">
                    <div class="col">
                        <a @click.prevent="select = 'payment-request'" href="">
                            <h5 class="text-primary">Запрос на оплату</h5>
                            <img src="/static/assets/img/payment-request.png">
                        </a>
                        <p class="text-secondary">
                            Запрос на оплату - позволяет выставить счет 
                            клиенту за товары и услуги в любой точке мира
                        </p>
                    </div>
                    <div class="col">
                        <a @click.prevent="" href="">
                            <h5 class="text-primary">Заявка на обмен</h5>
                            <img src="/static/assets/img/exchange.png">
                        </a>
                        <p class="text-secondary">
                            Заявка на обмен - обменивайте валюты и цифровые активы
                        </p>
                    </div>
                </div>
                <div v-if="select === 'payment-request'">
                    <h5 class="text-success">Запрос на оплату</h5>
                    <div class="row p-1">
                        <div class="col-md-auto border border-success rounded border-opacity-10 p-3">
                            <h6 class="text-secondary text-left">Редактор курсов</h6>
                            <div class="w-100 p-1"></div>
                            <convert-cur-block
                                ref="pr_cur_converter"
                                @changed="on_pr_cur_converter_change"
                            ></convert-cur-block>
                         </div>
                        <!-- 
                        <div class="row">
                            <div class="col-md-6">
                                <label class="form-label" style="float:left;">Сумма в валюте оплаты</label>
                                <input 
                                    ref="pr_src_amount"
                                    class="form-control"
                                    type="number" 
                                    v-model="payment_request.src.amount"
                                    placeholder="Введите сумму"
                                >
                            </div>
                            <div class="col-md-2">
                                <label class="form-label" style="float:left;">Валюта оплаты</label>
                                <input 
                                    ref="pr_src_currency"
                                    class="form-control"
                                    type="text" 
                                    v-model="payment_request.src.currency"
                                    placeholder=""
                                >
                            </div>
                        </div>
                        <div class="m-1">
                            <label class="form-label" style="float:left;">Назначение платежа</label>
                            <textarea
                                ref="pr_description"
                                class="form-control"
                                placeholder="Назначение платежа"
                                v-model="payment_request.description"
                            >
                            </textarea>
                        </div>
                        -->
                    </div>
                    <div class="row p-3">
                        <p class="text-danger">[[ payment_request.error ]]</p> 
                        <div class="col-1">
                            <span class="text-secondary">Отдают</span>
                        </div>
                        <div class="col-3">
                            <input 
                                    ref="pr_src_amount"
                                    class="form-control form-control-sm"
                                    type="number" 
                                    v-model="payment_request.src.amount"
                                    placeholder="сумма"
                                    @input="on_pr_amount('direct')"
                                >    
                        </div>
                        <span class="col-1 text-primary">[[ payment_request.src.currency ]]</span>
                        <span class="col-1">&rarr;</span>
                        <div class="col-3">
                            <input 
                                    ref="pr_dest_amount"
                                    class="form-control form-control-sm"
                                    type="number" 
                                    v-model="payment_request.destination.amount"
                                    placeholder="сумма"
                                    @input="on_pr_amount('revert')"
                                >       
                        </div>
                        <span class="col-1 text-primary">[[ payment_request.destination.currency ]]</span>
                    </div>
                    <div class="row" v-if="!payment_request.error">
                        <span class="text-primary col-3">
                            [[ payment_request.src.amount ]] [[ payment_request.src.currency ]]
                        </span>
                        <span class="col-1">&rarr;</span>
                        <span class="text-primary col-3">
                            [[ payment_request.src.amount ]] [[ payment_request.src.currency ]]
                        </span>
                    </div>
                    
                    <div class="w-100 border border-top border-secondary border-opacity-10 m-3"></div>
                    <div class="row p-3">
                        <div class="row p-3">
                            <div class="col-md-6">
                                <label class="form-label" style="float:left;">Стоимость услуги в локальной валюте</label>
                                <input 
                                    ref="pr_dest_amount"
                                    class="form-control"
                                    type="number" 
                                    v-model="payment_request.destination.amount"
                                    placeholder="Введите сумму"
                                >
                            </div>
                            <div class="col-md-2">
                                <label class="form-label" style="float:left;">Валюта услуги</label>
                                <input 
                                    ref="pr_dest_currency"
                                    class="form-control"
                                    type="text" 
                                    v-model="payment_request.destination.currency"
                                    placeholder=""
                                >
                            </div>
                        </div>
                        <div class="row p-3">
                            <div class="col-md-6">
                                <label class="form-label" style="float:left;">Монета взаиморасчетов</label>
                                <input 
                                    ref="pr_private_amount"
                                    class="form-control"
                                    type="text" 
                                    v-model="payment_request.private.token"
                                    disabled="disabled"
                                >
                            </div>
                            <div class="col-md-2">
                                <label class="form-label" style="float:left;">Курсы</label>
                                <input 
                                    ref="pr_private_source"
                                    class="form-control"
                                    type="text" 
                                    v-model="payment_request.private.source"
                                    disabled="disabled"
                                >
                            </div>
                        </div>  
                    </div>
                    <div class="w-100 text-center">
                        <button v-if="!loading" @click.prevent="submit" class="btn btn-primary">
                            Создать
                        </button>
                        <loader-circle v-if="loading"></loader-circle>
                        <p v-if="error_msg" class="text-danger">[[ error_msg ]]</p>
                    </div>  
                </div>
            </div>
        `
    }

);

Vue.component(
    'Orders',
    {
        props: {
            header: {
                type: String,
                default: "Orders"
            },
            merchant: {
                type: String,
                default: null
            },
            export_menu: {
                type: Array,
                default(){
                    return [
                        {
                            id: 'qugo',
                            label: 'qugo.ru Прямые выплаты [Excel]',
                            url_suffix: 'export?engine=qugo'
                        }
                    ]
                }
            }
        },
        delimiters: ['[[', ']]'],
        data() {
            return {
                items: [],
                loading: false,
                error_msg: null,
                icons: {
                    expanded: 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiIHN0YW5kYWxvbmU9Im5vIj8+CgoKCjwhLS0gTGljZW5zZTogUEQuIE1hZGUgYnkgamltbGFtYjogaHR0cHM6Ly9naXRodWIuY29tL2ppbWxhbWIvYm93dGllIC0tPgo8c3ZnIAogICB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iCiAgIHhtbG5zOmNjPSJodHRwOi8vY3JlYXRpdmVjb21tb25zLm9yZy9ucyMiCiAgIHhtbG5zOnJkZj0iaHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4LW5zIyIKICAgeG1sbnM6c3ZnPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIKICAgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIgogICB4bWxuczpzb2RpcG9kaT0iaHR0cDovL3NvZGlwb2RpLnNvdXJjZWZvcmdlLm5ldC9EVEQvc29kaXBvZGktMC5kdGQiCiAgIHhtbG5zOmlua3NjYXBlPSJodHRwOi8vd3d3Lmlua3NjYXBlLm9yZy9uYW1lc3BhY2VzL2lua3NjYXBlIgogICB3aWR0aD0iMzIwIgogICBoZWlnaHQ9IjQ0OCIKICAgdmlld0JveD0iMCAwIDMyMCA0NDgiCiAgIGlkPSJzdmcyIgogICB2ZXJzaW9uPSIxLjEiCiAgIGlua3NjYXBlOnZlcnNpb249IjAuOTEgcjEzNzI1IgogICBzb2RpcG9kaTpkb2NuYW1lPSJ0cmlhbmdsZS1yaWdodC1kb3duLnN2ZyI+CiAgPHRpdGxlCiAgICAgaWQ9InRpdGxlMzMzOCI+dHJpYW5nbGUtcmlnaHQtZG93bjwvdGl0bGU+CiAgPGRlZnMKICAgICBpZD0iZGVmczQiIC8+CiAgPHNvZGlwb2RpOm5hbWVkdmlldwogICAgIGlkPSJiYXNlIgogICAgIHBhZ2Vjb2xvcj0iI2ZmZmZmZiIKICAgICBib3JkZXJjb2xvcj0iIzY2NjY2NiIKICAgICBib3JkZXJvcGFjaXR5PSIxLjAiCiAgICAgaW5rc2NhcGU6cGFnZW9wYWNpdHk9IjAuMCIKICAgICBpbmtzY2FwZTpwYWdlc2hhZG93PSIyIgogICAgIGlua3NjYXBlOnpvb209IjEuOTc5ODk5IgogICAgIGlua3NjYXBlOmN4PSI3My4xNDAxMDgiCiAgICAgaW5rc2NhcGU6Y3k9IjIyMS45NzgxNyIKICAgICBpbmtzY2FwZTpkb2N1bWVudC11bml0cz0icHgiCiAgICAgaW5rc2NhcGU6Y3VycmVudC1sYXllcj0ibGF5ZXIxIgogICAgIHNob3dncmlkPSJ0cnVlIgogICAgIGZpdC1tYXJnaW4tdG9wPSI0NDgiCiAgICAgZml0LW1hcmdpbi1yaWdodD0iMzg0IgogICAgIGZpdC1tYXJnaW4tbGVmdD0iMCIKICAgICBmaXQtbWFyZ2luLWJvdHRvbT0iMCIKICAgICB1bml0cz0icHgiCiAgICAgaW5rc2NhcGU6d2luZG93LXdpZHRoPSIxNjgxIgogICAgIGlua3NjYXBlOndpbmRvdy1oZWlnaHQ9IjEzMzkiCiAgICAgaW5rc2NhcGU6d2luZG93LXg9IjEzMiIKICAgICBpbmtzY2FwZTp3aW5kb3cteT0iNDIzIgogICAgIGlua3NjYXBlOndpbmRvdy1tYXhpbWl6ZWQ9IjAiCiAgICAgaW5rc2NhcGU6c25hcC1iYm94PSJ0cnVlIgogICAgIGlua3NjYXBlOnNuYXAtYmJveC1lZGdlLW1pZHBvaW50cz0iZmFsc2UiCiAgICAgaW5rc2NhcGU6YmJveC1ub2Rlcz0idHJ1ZSI+CiAgICA8aW5rc2NhcGU6Z3JpZAogICAgICAgdHlwZT0ieHlncmlkIgogICAgICAgaWQ9ImdyaWQzMzQ3IgogICAgICAgc3BhY2luZ3g9IjE2IgogICAgICAgc3BhY2luZ3k9IjE2IgogICAgICAgZW1wc3BhY2luZz0iMiIKICAgICAgIG9yaWdpbng9IjAiCiAgICAgICBvcmlnaW55PSItMS43NDk4NDYyZS0wMDUiIC8+CiAgPC9zb2RpcG9kaTpuYW1lZHZpZXc+CiAgPG1ldGFkYXRhCiAgICAgaWQ9Im1ldGFkYXRhNyI+CiAgICA8cmRmOlJERj4KICAgICAgPGNjOldvcmsKICAgICAgICAgcmRmOmFib3V0PSIiPgogICAgICAgIDxkYzpmb3JtYXQ+aW1hZ2Uvc3ZnK3htbDwvZGM6Zm9ybWF0PgogICAgICAgIDxkYzp0eXBlCiAgICAgICAgICAgcmRmOnJlc291cmNlPSJodHRwOi8vcHVybC5vcmcvZGMvZGNtaXR5cGUvU3RpbGxJbWFnZSIgLz4KICAgICAgICA8ZGM6dGl0bGU+dHJpYW5nbGUtcmlnaHQtZG93bjwvZGM6dGl0bGU+CiAgICAgIDwvY2M6V29yaz4KICAgIDwvcmRmOlJERj4KICA8L21ldGFkYXRhPgogIDxnCiAgICAgaW5rc2NhcGU6bGFiZWw9IkxheWVyIDEiCiAgICAgaW5rc2NhcGU6Z3JvdXBtb2RlPSJsYXllciIKICAgICBpZD0ibGF5ZXIxIgogICAgIHRyYW5zZm9ybT0idHJhbnNsYXRlKDAsLTYwNC4zNjIyNCkiPgogICAgPHBhdGgKICAgICAgIHN0eWxlPSJmaWxsLXJ1bGU6ZXZlbm9kZDtzdHJva2U6bm9uZTtzdHJva2Utd2lkdGg6MXB4O3N0cm9rZS1saW5lY2FwOmJ1dHQ7c3Ryb2tlLWxpbmVqb2luOm1pdGVyO3N0cm9rZS1vcGFjaXR5OjEiCiAgICAgICBkPSJtIDI4Ny42NDY3NSw3NzYuNzE1NTEgMCwyMDMuNjQ2NzUgLTIwMy42NDY3NSwwIHoiCiAgICAgICBpZD0icGF0aDMzMzciCiAgICAgICBpbmtzY2FwZTpjb25uZWN0b3ItY3VydmF0dXJlPSIwIiAvPgogIDwvZz4KPC9zdmc+',
                    collapsed: 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiIHN0YW5kYWxvbmU9Im5vIj8+CgoKCjwhLS0gTGljZW5zZTogUEQuIE1hZGUgYnkgamltbGFtYjogaHR0cHM6Ly9naXRodWIuY29tL2ppbWxhbWIvYm93dGllIC0tPgo8c3ZnIAogICB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iCiAgIHhtbG5zOmNjPSJodHRwOi8vY3JlYXRpdmVjb21tb25zLm9yZy9ucyMiCiAgIHhtbG5zOnJkZj0iaHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4LW5zIyIKICAgeG1sbnM6c3ZnPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIKICAgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIgogICB4bWxuczpzb2RpcG9kaT0iaHR0cDovL3NvZGlwb2RpLnNvdXJjZWZvcmdlLm5ldC9EVEQvc29kaXBvZGktMC5kdGQiCiAgIHhtbG5zOmlua3NjYXBlPSJodHRwOi8vd3d3Lmlua3NjYXBlLm9yZy9uYW1lc3BhY2VzL2lua3NjYXBlIgogICB3aWR0aD0iMzIwIgogICBoZWlnaHQ9IjQ0OCIKICAgdmlld0JveD0iMCAwIDMyMCA0NDgiCiAgIGlkPSJzdmcyIgogICB2ZXJzaW9uPSIxLjEiCiAgIGlua3NjYXBlOnZlcnNpb249IjAuOTEgcjEzNzI1IgogICBzb2RpcG9kaTpkb2NuYW1lPSJ0cmlhbmdsZS1yaWdodC1vdXRsaW5lLnN2ZyI+CiAgPHRpdGxlCiAgICAgaWQ9InRpdGxlMzMzOCI+dHJpYW5nbGUtcmlnaHQtb3V0bGluZTwvdGl0bGU+CiAgPGRlZnMKICAgICBpZD0iZGVmczQiIC8+CiAgPHNvZGlwb2RpOm5hbWVkdmlldwogICAgIGlkPSJiYXNlIgogICAgIHBhZ2Vjb2xvcj0iI2ZmZmZmZiIKICAgICBib3JkZXJjb2xvcj0iIzY2NjY2NiIKICAgICBib3JkZXJvcGFjaXR5PSIxLjAiCiAgICAgaW5rc2NhcGU6cGFnZW9wYWNpdHk9IjAuMCIKICAgICBpbmtzY2FwZTpwYWdlc2hhZG93PSIyIgogICAgIGlua3NjYXBlOnpvb209IjEuOTc5ODk5IgogICAgIGlua3NjYXBlOmN4PSI3My4xNDAxMDgiCiAgICAgaW5rc2NhcGU6Y3k9IjIyMS45NzgxNyIKICAgICBpbmtzY2FwZTpkb2N1bWVudC11bml0cz0icHgiCiAgICAgaW5rc2NhcGU6Y3VycmVudC1sYXllcj0ibGF5ZXIxIgogICAgIHNob3dncmlkPSJ0cnVlIgogICAgIGZpdC1tYXJnaW4tdG9wPSI0NDgiCiAgICAgZml0LW1hcmdpbi1yaWdodD0iMzg0IgogICAgIGZpdC1tYXJnaW4tbGVmdD0iMCIKICAgICBmaXQtbWFyZ2luLWJvdHRvbT0iMCIKICAgICB1bml0cz0icHgiCiAgICAgaW5rc2NhcGU6d2luZG93LXdpZHRoPSIxNjgxIgogICAgIGlua3NjYXBlOndpbmRvdy1oZWlnaHQ9IjEzMzkiCiAgICAgaW5rc2NhcGU6d2luZG93LXg9IjEzMiIKICAgICBpbmtzY2FwZTp3aW5kb3cteT0iNDIzIgogICAgIGlua3NjYXBlOndpbmRvdy1tYXhpbWl6ZWQ9IjAiCiAgICAgaW5rc2NhcGU6c25hcC1iYm94PSJ0cnVlIgogICAgIGlua3NjYXBlOnNuYXAtYmJveC1lZGdlLW1pZHBvaW50cz0iZmFsc2UiCiAgICAgaW5rc2NhcGU6YmJveC1ub2Rlcz0idHJ1ZSI+CiAgICA8aW5rc2NhcGU6Z3JpZAogICAgICAgdHlwZT0ieHlncmlkIgogICAgICAgaWQ9ImdyaWQzMzQ3IgogICAgICAgc3BhY2luZ3g9IjE2IgogICAgICAgc3BhY2luZ3k9IjE2IgogICAgICAgZW1wc3BhY2luZz0iMiIKICAgICAgIG9yaWdpbng9IjAiCiAgICAgICBvcmlnaW55PSItMS43NDk4NDYyZS0wMDUiIC8+CiAgPC9zb2RpcG9kaTpuYW1lZHZpZXc+CiAgPG1ldGFkYXRhCiAgICAgaWQ9Im1ldGFkYXRhNyI+CiAgICA8cmRmOlJERj4KICAgICAgPGNjOldvcmsKICAgICAgICAgcmRmOmFib3V0PSIiPgogICAgICAgIDxkYzpmb3JtYXQ+aW1hZ2Uvc3ZnK3htbDwvZGM6Zm9ybWF0PgogICAgICAgIDxkYzp0eXBlCiAgICAgICAgICAgcmRmOnJlc291cmNlPSJodHRwOi8vcHVybC5vcmcvZGMvZGNtaXR5cGUvU3RpbGxJbWFnZSIgLz4KICAgICAgICA8ZGM6dGl0bGU+dHJpYW5nbGUtcmlnaHQtb3V0bGluZTwvZGM6dGl0bGU+CiAgICAgIDwvY2M6V29yaz4KICAgIDwvcmRmOlJERj4KICA8L21ldGFkYXRhPgogIDxnCiAgICAgaW5rc2NhcGU6bGFiZWw9IkxheWVyIDEiCiAgICAgaW5rc2NhcGU6Z3JvdXBtb2RlPSJsYXllciIKICAgICBpZD0ibGF5ZXIxIgogICAgIHRyYW5zZm9ybT0idHJhbnNsYXRlKDAsLTYwNC4zNjIyNCkiPgogICAgPHBhdGgKICAgICAgIHN0eWxlPSJmaWxsLXJ1bGU6ZXZlbm9kZDtzdHJva2U6bm9uZTtzdHJva2Utd2lkdGg6MXB4O3N0cm9rZS1saW5lY2FwOmJ1dHQ7c3Ryb2tlLWxpbmVqb2luOm1pdGVyO3N0cm9rZS1vcGFjaXR5OjEiCiAgICAgICBkPSJNIDk2IDg4IEwgOTYgMzc2IEwgMjQwIDIzMiBMIDk2IDg4IHogTSAxMjggMTY4IEwgMTk2IDIzMiBMIDEyOCAyOTYgTCAxMjggMTY4IHogIgogICAgICAgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMCw2MDQuMzYyMjQpIgogICAgICAgaWQ9InBhdGgzMzM3IiAvPgogIDwvZz4KPC9zdmc+',
                },
                labels: {
                    export: 'Экспорт',
                    bank_account: 'Реквизиты',
                    description: 'Описание',
                    amount: 'Сумма',
                    identity: 'Идентификатор',
                    refresh: 'Обновить',
                    mass_payment: 'Массовые выплаты',
                    mass_operations: 'Массовые операции',
                    mass_operations_details: 'Здесь Вы можете одним действием проводить массовое редактирование ордеров на выплату',
                    empty_orders_alarm: 'У Вас пока нет активных заявок',
                    deposit_wait_approve: 'Депозиты ожидаются',
                    customer: 'Имя',
                    currency: 'Валюта'
                },
                selected_row: null,
                preview_info: null,
                preview_history: null,
                selected_row_editing: false,
                window_height: 500,
                editing: null,
                selected_deposit: null,
                modal_new_order: false,
                refresh_counter: 0,
                payment_request_table: {
                    headers: [
                        {label: 'No', sortable: true},
                        {label: 'Имя', sortable: true},
                        {label: 'Сумма', sortable: true},
                        {label: 'Описание', sortable: false}
                    ],
                    rows: [],
                    collapsed: false
                }
            }
        },
        mounted(){
            this.window_height = window.innerHeight;
            this.refresh();
        },
        computed: {
            mass_payment_items(){
                if (this.refresh_counter < 0){
                    return []
                }
                let items = [];
                for (let i=0; i<this.items.length; i++) {
                    const order = this.items[i];
                    if (order.type === 'mass-payment') {
                        items.push(order);
                    }
                }
                return items;
            },
            payment_request_items(){
                if (this.refresh_counter < 0){
                    return []
                }
                let items = [];
                for (let i=0; i<this.items.length; i++) {
                    const order = this.items[i];
                    if (order.type === 'payment-request') {
                        items.push(order);
                    }
                }
                return items;
            }
        },
        methods: {
            cell_btn_clicked(id, row, col, row_id) {
                //console.log('Btn clicked ID: ' + id + ' row: ' + row + ' col: ' + col + ' row-id: ' + row_id);
            },
            cell_link_clicked(id, row, col, row_id) {
                //console.log('Link clicked ID: ' + id + ' row: ' + row + ' col: ' + col + ' row-id: ' + row_id);
            },
            cell_clicked(id, row, col, row_id) {
                //console.log('Cell clicked ID: ' + id + ' row: ' + row + ' col: ' + col + ' row-id: ' + row_id);
            },
            row_select(row, order_uid, type='mass-payment') {
                this.selected_row_editing = false;
                const order = this.extract_order(order_uid);
                if (order) {
                    this.selected_row = {
                        order: order,
                        type: type
                    };
                    if (type === 'mass-payment') {
                        //console.log(order.api);
                        this.load_order_preview(order.api);
                    }
                    else {
                        console.error('Not implemented!')
                    }
                }
                else {
                    this.selected_row = null;
                }
            },
            clicked_export_dropdown(){
                let width = $(this.$refs.export_menu_btn).width();
                $(this.$refs.export_menu).css({'margin-left': width*1.5}).toggle();
            },
            clicked_export_menu(id, api=null){
                if (api) {
                    let url = null;
                    for(let i=0; i<this.export_menu.length;i++) {
                        if (this.export_menu[i].id === id) {
                            url = api + '/' + this.export_menu[i].url_suffix;
                            break;
                        }
                    }
                    if (url != null) {
                        window.open(url, '_blank').focus();
                    }
                    console.log()
                }
                $(this.$refs.export_menu).hide();
            },
            extract_order(order_uid){
                for (let i=0; i<this.items.length; i++) {
                    let item = this.items[i];
                    if (item.type === 'mass-payment') {
                        for (let j=0; j<item.batch.orders.length; j++) {
                            let order = item.batch.orders[j];
                            if (order.uid === order_uid) {
                                return order;
                            }
                        }
                    }
                    else if (item.type === 'simple-payment') {
                        let order = item.order;
                        if (order.uid === order_uid){
                            return item.order;
                        }
                    }
                }
                return null;
            },
            load_order_preview(url){
                this.preview_info = null;
                this.preview_history = null;
                let self = this;
                axios
                   .get(url)
                   .then(
                       (response) => {
                           self.preview_info = response.data;
                           //console.log(response.data)
                       }
                   ).catch(
                        (e) => {
                           self.preview_info = {
                               error_msg: e.message || e.response.statusText
                           }
                        }
                   )
                axios
                   .get(url + '/history')
                   .then(
                       (response) => {
                           let history = [];
                           let file_url = url.split('/').slice(0, -1).join('/');
                           for (let i=0; i<response.data.length; i++) {
                               let item = response.data[i];
                               item.utc = format_datetime_str(item.utc);
                               item.attachments = [];
                               if (item.payload && item.payload.attachments) {
                                   let attachments = [];
                                   for (let j=0; j<item.payload.attachments.length; j++) {
                                       let a = item.payload.attachments[j];
                                       a.url = file_url + '/' + a.uid + '/file';
                                       attachments.push(a);
                                   }
                                   item.attachments = attachments;
                               }
                               history.push(item);
                           }
                           self.preview_history = history;
                           //console.log(response.data)
                       }
                   ).catch(
                        (e) => {
                           self.preview_history = {
                               error_msg: e.message || e.response.statusText
                           }
                        }
                   )
            },
            refresh(){
                let self = this;
                self.loading = true;
                self.error_msg = null;
                self.selected_row = null;
                axios
                   .get('/api/orders')
                   .then(
                       (response) => {
                           let new_items = [];

                           for (let i=0; i<response.data.length; i++) {
                               let item = self.build_item(response.data[i]);
                               new_items.push(item);
                           }
                           self.items = new_items;
                           //this.info = response
                           self.refresh_counter += 1;
                           self.build_payment_request_table();
                           const form = self.$refs['table-payment-requests'];
                           if (form) {
                               form.refresh(
                                   self.payment_request_table.rows
                               );
                           }
                       }
                   ).catch(
                        (e) => {
                           self.error_msg = e.message || e.response.statusText;
                        }
                   ).finally(
                       response => (
                           self.loading = false
                       )
                   )
            },
            build_item(order) {
                let item = {}
                item.id = order.id;
                item.type = order.type;
                item.collapsed = false;
                if (item.type === 'mass-payment') {
                    item.batch = order.batch;
                    // rebuild attachments
                    let attachments = []
                    for (let j=0; j<item.batch.attachments.length; j++) {
                        let a = item.batch.attachments[j];
                        a.url = order.batch.ledger.api + '/' + a.uid + '/file'
                        attachments.push(a);
                    }
                    item.batch.attachments = attachments;
                    item.label = order.batch.ledger.title + ' ' + this.labels.mass_payment;
                    item.api = order.batch.ledger.api;
                    item.role = order.batch.ledger.role;
                    item.deposits = [];
                    for (let i=0; i<order.batch.deposits.length; i++) {
                        const dep = order.batch.deposits[i];
                        dep.api = order.batch.ledger.api + '/' + dep.uid + '/deposit';
                        dep.batch_id = item.id;
                        item.deposits.push(dep);
                    }
                    let rows = [];
                    for (let i=0; i<order.batch.orders.length; i++) {
                        let order_ = order.batch.orders[i];
                        order_.api = item.api + '/' + order_.uid;
                        order_.ledger = item.batch.ledger;
                        let account = '';
                        let holder = '';
                        if (order_.details.card) {
                            account = order_.details.card.number;
                            try {
                                account = cc_format(order_.details.card.number);
                                holder = order_.details.card.holder;
                            }catch (e) {
                                console.log(e)
                            }
                        }

                        let row = {
                            id: order_.uid,
                            cells: [
                                {
                                    id: 'txn',
                                    text: order_.id,
                                    class: 'text-primary',
                                    badges: [
                                        {
                                            label: 'processing',
                                            style: 'margin-left: 5px;',
                                            class: 'text-success'
                                        }
                                    ],
                                    icon: {
                                        src: '/static/assets/img/pending-green2.gif',
                                        style: 'max-height: 15px;margin-left:4px;'
                                    }
                                },
                                {
                                    id: 'account',
                                    text: account,
                                    badges: [
                                        {
                                            label: holder ? 'Holder: ' + holder : '',
                                            style: 'margin-left: 10px;',
                                            class: 'badge bg-secondary'
                                        }
                                    ]
                                },
                                {
                                    id: 'amount',
                                    text: new Intl.NumberFormat().format(order_.amount),
                                    badges: [
                                        {
                                            label: order_.currency,
                                            style: 'margin-left: 5px;',
                                            class: 'badge bg-primary'
                                        }
                                    ]
                                },
                                {
                                    id: 'description',
                                    text: order_.description
                                },
                                {
                                    id: 'identity',
                                    text: order_.customer
                                },
                                {
                                    id: 'payload',
                                    payload: order_
                                }
                            ]
                        };
                        rows.push(row)
                    }
                    item.table = {
                        headers: [
                            {label: 'Txn', sortable: true},
                            {label: this.labels.bank_account, sortable: true},
                            {label: this.labels.amount, sortable: true},
                            {label: this.labels.description, sortable: false},
                            {label: this.labels.identity, sortable: true},
                            {hidden: true}
                        ],
                        rows: rows
                    }
                }
                else if (item.type === 'payment-request') {
                    item.payment_request = order.payment_request
                }
                return item;
            },
            refresh_batch(batch_id) {
                const comps = this.$refs['table-' + batch_id];
                const self = this;
                if (comps) {
                    const comp = comps[0];
                    comp.set_loading(true);
                    comp.set_error(null);
                    axios
                       .get('/api/orders/' + batch_id)
                       .then(
                           (response) => {
                               const new_value = response.data;
                               for (let i=0; i<self.items.length; i++) {
                                   if (self.items[i].id === batch_id) {
                                       if (new_value) {
                                           let new_item = self.build_item(new_value);
                                           for (let attr in self.items[i]) {
                                               self.items[i][attr] = new_item[attr];
                                           }
                                       }
                                       else {
                                           self.items[i].table.rows = [];
                                       }
                                       comp.refresh(self.items[i].table.rows);
                                       return
                                   }
                               }
                               //console.log(new_value)
                           }
                       ).catch(
                            (e) => {
                                if (e.response && e.response.status == 404) {
                                    for (let i=0; i<self.items.length; i++) {
                                       if (self.items[i].id === batch_id) {
                                           self.items[i].table.rows = [];
                                           self.items[i].deposits = [];
                                           comp.refresh(self.items[i].table.rows);
                                           return
                                       }
                                   }
                                }
                                else {
                                    comp.set_error(e.message || e.response.statusText)
                                }
                            }
                       ).finally(
                           response => (
                               comp.set_loading(false)
                           )
                       )
                }
            },
            build_payment_request_table(){
                let rows = [];
                let items = this.payment_request_items;
                for (let i=0; i<items.length; i++) {
                    let req = items[i].payment_request;
                    let row = {
                        id: req.uid,
                        cells: [
                            {
                                id: 'no',
                                text: req.id,
                                class: 'text-primary',
                            },
                            {
                                id: 'customer',
                                text: req.customer
                            },
                            {
                                id: 'amount',
                                text: new Intl.NumberFormat().format(req.amount),
                                badges: [
                                    {
                                        label: req.currency,
                                        style: 'margin-left: 5px;',
                                        class: 'badge bg-primary'
                                    }
                                ]
                            },
                            {
                                id: 'description',
                                text: req.description
                            }
                        ]
                    };
                    rows.push(row)
                }
                this.payment_request_table.rows = rows;

            },
            toggle_batch(item) {
                item.collapsed = !item.collapsed
            },
            on_selected_batched_order_edit(on){
                this.selected_row_editing = on;
            },
            on_selected_batched_order_apply(status, attachments, message){
                //console.log('Apply: status: ' + status + '  message: ' + message)
                //console.log(attachments);
                const self = this;
                const comp = self.$refs.status_editor;
                if (this.selected_row.type === 'mass-payment') {
                    self.$refs.status_editor.set_loading(true);
                    const url_status_edit = self.selected_row.order.ledger.api + '/status';
                    const url_update = self.selected_row.order.api;
                    const batch_id = self.selected_row.order.ledger.id;

                    let json = this.build_status_edit_json(
                        this.selected_row.order.uid,
                        status,
                        attachments,
                        message
                    );

                    const payload = JSON.stringify(json);
                    const config = {
                        headers: {'Content-Type': 'application/json'}
                    }
                    axios
                       .post(
                           url_status_edit, payload, config
                       )
                       .then(
                           (response) => {
                               comp.enable_edit(false);
                               self.selected_row_editing = false;
                               self.load_order_preview(url_update);
                               self.refresh_batch(batch_id);
                           }
                       ).catch(
                            (e) => {
                               comp.set_error(e.message || e.response.statusText);
                            }
                       )
                }
            },
            on_mass_batched_order_apply(batch_id, status, attachments, message){
                //console.log('Apply: status: ' + status + '  message: ' + message)
                //console.log(attachments);
                const self = this;
                const ref_name = "multi_status_editor-" + batch_id
                const comp = self.$refs[ref_name][0];
                comp.set_loading(true);
                let batch = null;
                for (let i=0; i<this.items.length; i++) {
                    if (this.items[i].id === batch_id) {
                        batch = this.items[i].batch;
                        break;
                    }
                }
                if (batch === null) {
                    console.log('Batch with id ' + batch_id + ' not found!');
                    return;
                }
                const url_status_edit = batch.ledger.api + '/status';
                let uids = [];
                for (let i in batch.orders) {
                    let order = batch.orders[i];
                    uids.push(order.uid);
                }

                let json = this.build_status_edit_json(
                    uids,
                    status,
                    attachments,
                    message
                );
                const payload = JSON.stringify(json);
                const config = {
                    headers: {'Content-Type': 'application/json'}
                }
                self.error_msg = null;
                axios
                   .post(
                       url_status_edit, payload, config
                   )
                   .then(
                       (response) => {
                           comp.enable_edit(false);
                           self.refresh_batch(batch_id);
                       }
                   ).catch(
                        (e) => {
                           comp.set_error(e.message || e.response.statusText);
                        }
                   )
            },
            show_attachments(items){
                this.$refs.files_navigator.open(items);
            },
            build_status_edit_json(uid, status, attachments, message){
                let json = [];
                let payload_attachments = [];
                for (let i=0; i<attachments.length; i++) {
                    const a = attachments[i];
                    let d = {
                        uid: a.uid,
                        name: a.name,
                        data: a.data
                    }
                    if (a.mime_type) {
                        d.mime_type = a.mime_type
                    }
                    json.push(d);
                    payload_attachments.push({
                        uid: a.uid,
                    })
                }
                let uids = [];
                if (typeof(uid) === 'string') {
                    uids.push(uid)
                }
                else {
                    uids = uid;
                }
                for (let i in uids) {
                    let upd = {
                        uid: uids[i],
                        status: status,
                    }
                    if (payload_attachments.length > 0) {
                        upd.payload = {
                            attachments: payload_attachments
                        }
                    }
                    if (message) {
                        upd.message = message;
                    }
                    json.push(upd);
                }
                return json;
            },
            approve_deposit(model, mode='accept'){
                let editing_obj = {}
                for (let attr in model) {
                    if (attr === 'utc') {
                        editing_obj[attr] = format_datetime_str(model[attr]);
                    }
                    else {
                        editing_obj[attr] = model[attr];
                    }
                }
                editing_obj.mode = mode;
                editing_obj.loading = false;
                editing_obj.error_msg = null;
                this.selected_deposit = editing_obj;
            },
            send_selected_deposit(mode='accept') {
                const status = mode === 'accept' ? 'success' : 'error';
                const url = this.selected_deposit.api;
                const self = this;
                self.selected_deposit.loading = true;

                axios
                   .post(
                       url,
                       JSON.stringify(
                           {
                               amount: self.selected_deposit.amount,
                               status: status
                           }
                       ),
                       {
                    headers: {'Content-Type': 'application/json'}
                }
                   )
                   .then(
                       (response) => {
                           self.refresh_batch(self.selected_deposit.batch_id);
                           self.selected_deposit = null;
                       }
                   ).catch(
                        (e) => {
                           self.selected_deposit.error_msg = e.message || e.response.statusText;
                        }
                   ).finally(
                        (response) => {
                            if (self.selected_deposit) {
                                self.selected_deposit.loading = false
                            }
                        }
                   )
            },
        },
        template: `
            <div class="w-100 text-center">
                
                <div v-if="error_msg" class="alert alert-danger text-center">
                    <p>[[ error_msg ]]</p>
                </div>
                <div class="w-100 text-center" v-if="loading">
                    <loader></loader>
                </div>
                <div class="alert alert-primary" v-if="items.length == 0 && !error_msg && !loading">
                    [[ labels.empty_orders_alarm ]]
                </div>
                
                <modal-window v-if="selected_row" @close="selected_row = null" :width="'70%'">
                    <div slot="header" class="w-100">
                        <h3 class="text-primary"><b class="text-dark">Txn: </b> [[ selected_row.order.id ]] 
                            <b class="text-dark">[[ labels.identity ]]: </b>[[ selected_row.order.customer ]]
                            <button class="btn btn-danger" @click="selected_row = null" style="float: right;">
                                Close
                            </button>
                        </h3>
                    </div>
                    <div slot="body" class="w-100 text-center" v-bind:style="{'overflow': 'hidden', 'height': 4*window_height/5 + 'px'}">
                        <div class="w-100 row">
                            <div class="col">
                                <h4 class="rounded p-1 text-primary alert alert-primary">
                                    Info
                                </h4>
                                <div>
                                    <loader-circle v-if="!preview_info"></loader-circle>
                                    <div v-if="preview_info && preview_info.error_msg" class="alert alert-danger text-center">
                                        [[ preview_info.error_msg ]]
                                    </div>
                                    
                                    <mass-payment-order-status-editor
                                        ref="status_editor"
                                        v-if="preview_info && !preview_info.error_msg"
                                        class="mt-3"
                                        :default_status="selected_row.order.ledger.role == 'processing' ? 'success' : 'attachment'"    
                                        :available_statuses="selected_row.order.ledger.role == 'processing' ? null : ['attachment']"
                                        @on_edit="(on) => {on_selected_batched_order_edit(on)}"
                                        @on_apply="(s, atts, msg) => {on_selected_batched_order_apply(s, atts, msg)}"
                                    ></mass-payment-order-status-editor>
                                    <div class="border-top my-3"></div>
                                    
                                    <div v-if="preview_info && !preview_info.error_msg && !selected_row_editing" class="p-2" v-bind:style="{'overflow': 'auto', 'height': 2*window_height/3 + 'px', 'text-align': 'left'}">
                                        <!-- -->
                                        <object-info 
                                            :object="preview_info.status"
                                            :hidden="['payload']"
                                            :header="'Status'"
                                            :attr_class="{
                                                'false': 'text-secondary',
                                                'true': 'text-success',
                                                'error': 'badge bg-danger',
                                                'message': 'badge bg-info',
                                                'pending': 'badge bg-primary',
                                                'success': 'badge bg-success',
                                                'processing': 'badge bg-primary',
                                                'type': 'badge bg-secondary'
                                            }"
                                        >
                                        </object-info>
                                        <!-- -->
                                        <object-info
                                            :object="preview_info.proof"
                                            :header="'Proof'"
                                        >
                                        </object-info>
                                        <!-- -->
                                        <object-info 
                                            :object="preview_info.transaction"
                                            :header="'Transaction'"
                                        >
                                        </object-info>
                                        <!-- -->
                                        <object-info 
                                            :object="preview_info.customer"
                                            :header="'Customer'"
                                        >
                                        </object-info>
                                        <!-- -->
                                        <object-info 
                                            :object="preview_info.card"
                                            :header="'Card'"
                                        >
                                        </object-info>
                                    </div>
                                </div>
                            </div>
                            <div class="col">
                                <h4 class="rounded p-1 text-primary alert alert-primary">
                                    History
                                </h4>
                                <div>
                                    <loader-circle v-if="!preview_history"></loader-circle>
                                    <div v-if="preview_history && preview_history.error_msg" class="alert danger text-center">
                                        [[ preview_history.error_msg ]]
                                    </div>
                                </div>
                                <div v-if="preview_history && !preview_history.error_msg" class="p-2" v-bind:style="{'overflow': 'auto', 'height': 3*window_height/4 + 'px', 'text-align': 'left'}">
                                    <li class="w-100" v-for="item in preview_history">
                                        <span class="text-secondary">utc: [[ item.utc ]]</span>
                                        <span 
                                            style="margin-left: 10px;"
                                            class="badge"
                                            v-bind:class="{'bg-danger': item.status === 'error', 'bg-success': item.status === 'success', 'bg-secondary': ['attachment', 'created'].includes(item.status), 'bg-primary': item.status === 'processing'}"
                                        >
                                            [[item.status]]
                                        </span>
                                        <br/>
                                        <div class="border border-opacity-50 rounded p-2 m-1" style="margin-left: 50px;" v-if="item.message || item.attachments.length > 0">
                                            <span v-if="item.message" class="text-secondary">Message: </span>
                                            <span v-if="item.message">[[ item.message ]]</span>
                                            <br v-if="item.message" />
                                            <span v-if="item.attachments.length > 0" class="text-secondary">Attachments ([[ item.attachments.length ]]): </span>
                                            <div v-if="item.attachments" v-for="a in item.attachments">
                                                <a v-bind:href="a.url">
                                                    [[a.name]]
                                                </a>
                                            </div>
                                        </div>
                                    </li>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div slot="footer" class="w-100 text-center">
                        
                    </div>
                </modal-window>
                
                <modal-window v-if="selected_deposit" @close="selected_deposit = null" :width="'30%'">
                    <div slot="header" class="w-100">
                        <h3 class="text-primary"><b class="text-dark">Deposit: </b>[[ selected_deposit.uid ]]
                            <button class="btn btn-danger" @click="selected_deposit = null" style="float: right;">
                                Close
                            </button>
                        </h3>
                    </div>
                    <div slot="body" class="w-100 text-left p-3 border rounded border-opacity-50">
                        <ul style="list-style: none;text-align: left;">
                            <li class="m-1">
                                <span class="text-secondary">Amount ([[ selected_deposit.currency ]]):</span>
                                <input class="form-control" type="number" v-model="selected_deposit.amount" />
                            </li>
                            <li class="m-1">
                                <span class="text-secondary">UTC:</span>
                                <span>[[ selected_deposit.utc ]]</span>
                            </li>
                            <li class="m-1">
                                <span class="text-secondary">Address:</span>
                                <span>[[ selected_deposit.address ]]</span>
                            </li>
                            <li class="m-1">
                                <span class="text-secondary">Method:</span>
                                <span>[[ selected_deposit.pay_method_code ]]</span>
                            </li>
                        </ul>
                        <div class="w-100 text-center">
                            <p v-if="selected_deposit.mode === 'accept'" class="alert alert-success">Are you sure?</p>
                            <button 
                                @click.prevent="send_selected_deposit('accept')" 
                                v-if="selected_deposit.mode === 'accept' && !selected_deposit.loading" 
                                class="btn btn-success"
                            >Accept</button>
                            
                            <p v-if="selected_deposit.mode === 'reject'" class="alert alert-danger">Are you sure?</p>
                            <button 
                                @click.prevent="send_selected_deposit('reject')" 
                                v-if="selected_deposit.mode === 'reject' && !selected_deposit.loading" 
                                class="btn btn-danger"
                            >Reject</button>
                            
                            <img v-if="selected_deposit.loading" style="max-height:25px;" src="/static/assets/img/pending-green2.gif"/>
                        </div>
                    </div>
                    <div slot="footer" class="w-100 text-center">
                    </div>
                </modal-window>
                
                <modal-window v-if="modal_new_order" @close="modal_new_order = false" :width="'50%'" >
                    <div slot="header" class="w-100">
                        <h3 class="text-primary">Создание заявки
                            <button class="btn btn-danger" @click="modal_new_order = false" style="float: right;">
                                Close
                            </button>
                        </h3>
                    </div>
                    <div slot="body" class="w-100 text-left p-3 border rounded border-opacity-50" v-bind:style="{'overflow': 'auto'}">
                        <create-order
                            @on_success="() => {refresh(); modal_new_order = false}"
                        >
                        </create-order>
                    </div>
                    <div slot="footer" class="w-100 text-center">
                    </div>
                </modal-window>
                
                <files-navigator-modal
                    ref="files_navigator" 
                >
                </files-navigator-modal>
                
                <div class="accordion" id="accordionOrders">
                  <!-- Кнопка добавления заявки -->
                  <div class="w-100 text-center m-1" style="height:50px;">
                      <a @click.prevent="modal_new_order = true" class="text-success" href="">
                          <svg style="height:100%;width:max-content;" xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-plus-square-dotted" viewBox="0 0 16 16">
                              <path d="M2.5 0q-.25 0-.487.048l.194.98A1.5 1.5 0 0 1 2.5 1h.458V0zm2.292 0h-.917v1h.917zm1.833 0h-.917v1h.917zm1.833 0h-.916v1h.916zm1.834 0h-.917v1h.917zm1.833 0h-.917v1h.917zM13.5 0h-.458v1h.458q.151 0 .293.029l.194-.981A2.5 2.5 0 0 0 13.5 0m2.079 1.11a2.5 2.5 0 0 0-.69-.689l-.556.831q.248.167.415.415l.83-.556zM1.11.421a2.5 2.5 0 0 0-.689.69l.831.556c.11-.164.251-.305.415-.415zM16 2.5q0-.25-.048-.487l-.98.194q.027.141.028.293v.458h1zM.048 2.013A2.5 2.5 0 0 0 0 2.5v.458h1V2.5q0-.151.029-.293zM0 3.875v.917h1v-.917zm16 .917v-.917h-1v.917zM0 5.708v.917h1v-.917zm16 .917v-.917h-1v.917zM0 7.542v.916h1v-.916zm15 .916h1v-.916h-1zM0 9.375v.917h1v-.917zm16 .917v-.917h-1v.917zm-16 .916v.917h1v-.917zm16 .917v-.917h-1v.917zm-16 .917v.458q0 .25.048.487l.98-.194A1.5 1.5 0 0 1 1 13.5v-.458zm16 .458v-.458h-1v.458q0 .151-.029.293l.981.194Q16 13.75 16 13.5M.421 14.89c.183.272.417.506.69.689l.556-.831a1.5 1.5 0 0 1-.415-.415zm14.469.689c.272-.183.506-.417.689-.69l-.831-.556c-.11.164-.251.305-.415.415l.556.83zm-12.877.373Q2.25 16 2.5 16h.458v-1H2.5q-.151 0-.293-.029zM13.5 16q.25 0 .487-.048l-.194-.98A1.5 1.5 0 0 1 13.5 15h-.458v1zm-9.625 0h.917v-1h-.917zm1.833 0h.917v-1h-.917zm1.834-1v1h.916v-1zm1.833 1h.917v-1h-.917zm1.833 0h.917v-1h-.917zM8.5 4.5a.5.5 0 0 0-1 0v3h-3a.5.5 0 0 0 0 1h3v3a.5.5 0 0 0 1 0v-3h3a.5.5 0 0 0 0-1h-3z"/>
                          </svg>
                          <span class="margin-left:3%;">Создать заявку</span> 
                      </a>
                  </div>
                  
                  <!--- Панель массовых выплат -->
                  <div class="card" v-bind:class="{'border-dark': !item.collapsed}" v-for="(item, index) in mass_payment_items">
                     <div class="card-header">
                      <h5 class="mb-0" style="text-align: left;">
                        <button @click="toggle_batch(item)" class="btn btn-link" type="button">
                          <img style="max-height: 20px;max-width:20px;margin-right: 5px;" 
                            v-bind:src="item.collapsed ? icons.collapsed : icons.expanded" 
                          />
                            [[ item.label ]]
                        </button>
                        <button @click.prevent="refresh_batch(item.id)" class="btn btn-primary btn-sm" v-bind:title="labels.refresh">
                            <i class="fa-solid fa-rotate"></i>
                        </button>
                      </h5>
                    </div>
                    <div v-bind:class="{'collapse': item.collapsed }">
                      <div class="card-body">
                        <div class="row">
                            <div class="col-sm-5 align-items-stretch">
                                <div class="card-title">
                                  <h6>[[ labels.mass_operations ]]
                                    <div class="btn-group" v-if="item.role == 'processing'">
                                      <button @click="clicked_export_dropdown"  ref="export_menu_btn" class="btn btn-secondary btn-sm" type="button">
                                        [[ labels.export ]]
                                      </button>
                                      <button @click="clicked_export_dropdown"  type="button" class="btn btn-sm btn-secondary dropdown-toggle dropdown-toggle-split" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                                        <span class="sr-only"></span>
                                      </button>
                                      <div class="dropdown-menu" ref="export_menu">
                                            <a @click.prevent="clicked_export_menu(menu.id, item.api)" 
                                               class="dropdown-item" href="#" v-for="menu in export_menu"
                                            >[[ menu.label ]]</a>
                                      </div>
                                    </div>
                                  </h6>
                                  <p class="text-secondary">
                                    [[ labels.mass_operations_details ]]
                                    <a 
                                        v-if="item.batch.attachments.length > 0"
                                        @click.prevent="show_attachments(item.batch.attachments)" 
                                        href="" 
                                        class="text-primary" 
                                        style="margin-left:10px;"
                                    >
                                        <i class="fa-regular fa-file"></i>
                                        Attachments ([[ item.batch.attachments.length ]])
                                    </a>
                                  </p>
                                  
                                </div>
                                <div class="card-body">
                                  <mass-payment-order-status-editor
                                        v-bind:ref="'multi_status_editor-' + item.id"
                                        :default_status="item.batch.ledger.role == 'processing' ? 'success' : 'attachment'"    
                                        :available_statuses="item.batch.ledger.role == 'processing' ? null : ['attachment']"
                                        @on_apply="(s, atts, msg) => {on_mass_batched_order_apply(item.id, s, atts, msg)}"
                                  ></mass-payment-order-status-editor>
                                </div>
                            </div>
                            <div class="col">
                                <div class="w-100" style="text-align: left;" v-if="item.role == 'processing' && item.deposits.length > 0">
                                    <span class="text-success">[[ labels.deposit_wait_approve ]]</span>
                                    <ul style="list-style: none;">
                                        <li v-for="deposit in item.deposits" class="p-1">
                                            <img style="max-height:20px;" src="/static/assets/img/pending-green.gif" />
                                            <a class="text-danger" href="" @click.prevent="">
                                              <b>[[ deposit.amount ]]</b> [[ deposit.currency ]]
                                            </a> 
                                            &ensp;&ensp;
                                            <a @click.prevent="approve_deposit(deposit, 'accept')" href="" class="text-success">✔ accept</a>
                                            &ensp;&ensp;
                                            <a @click.prevent="approve_deposit(deposit, 'reject')" href="" class="text-danger">✕ reject</a>
                                        </li>
                                    </ul>
                                    
                                </div>
                                <data-table
                                    v-bind:ref="'table-' + item.id"
                                    style="text-align: left;"
                                    :headers="item.table.headers"
                                    :rows="item.table.rows"
                                    @click_btn="cell_btn_clicked"
                                    @click_link="cell_link_clicked"
                                    @click_cell="cell_clicked"
                                    @select_row="row_select"
                                ></data-table>
                            </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <!-- Панель заявок на оплату -->
                  <div class="w-100 m-1" v-if="mass_payment_items.length>0"></div>
                  <div 
                    class="card" 
                    v-bind:class="{'border-dark': !payment_request_table.collapsed}" 
                    v-if="payment_request_items.length > 0"
                  >
                      <div class="card-header">
                          <h5 class="mb-0" style="text-align: left;">
                            <button 
                                @click="payment_request_table.collapsed = !payment_request_table.collapsed" 
                                class="btn btn-link" 
                                type="button"
                            >
                              <img style="max-height: 20px;max-width:20px;margin-right: 5px;" 
                                v-bind:src="payment_request_table.collapsed ? icons.collapsed : icons.expanded" 
                              />
                                 Запрос на оплату
                            </button>
                          </h5>
                      </div>
                      <div v-bind:class="{'collapse': payment_request_table.collapsed }">
                         <div class="card-body">
                            <data-table
                                ref="table-payment-requests"
                                style="text-align: left;"
                                :headers="payment_request_table.headers"
                                :rows="payment_request_table.rows"
                                @select_row="row_select"
                            ></data-table>
                         </div>
                      </div>  
                  </div>
                </div>
            </div>
        `
    }
);

Vue.component(
    'Portfolio',
    {
        props: {
            header: {
                type: String,
                default: "Портфолио"
            },
        },
        delimiters: ['[[', ']]'],
        data() {
            return {
                loaded: false,
                portfolio: null,
                labels: {
                    title_account: 'Аккаунт',
                    title_merchant: 'Мерчант'
                }
            }
        },
        mounted(){
            this.refresh();
        },
        methods: {
            refresh(){
                let self = this;
                self.loaded = false;
                console.log('Refresh portfolio');
                axios
                    .get('/api/accounts/iam')
                    .then(
                        response => (
                            self.portfolio = response.data
                            //this.info = response
                        )
                    ).finally(
                        response => (
                            self.loaded = true
                        )
                )
            }
        },
        template: `
            <div class="w-100">
                <div class="card mb-4">
                    <div class="card-header">
                        <h5 class="card-title">[[ labels.title_account ]]</h5>
                    </div>
                    <div class="card-body">
                        <account-info :account="portfolio"></account-info>
                    </div>
                </div>
                
                
                <div class="card mb-4" v-if="portfolio && portfolio.merchant_meta">
                    <div class="card-header">
                        <h5 class="card-title">[[ labels.title_merchant ]]</h5>
                    </div>
                    <div class="card-body">
                        <merchant-info :merchant="portfolio.merchant_meta"></merchant-info>
                    </div>
                </div>
            </div>
        `
    }
);

Vue.component(
    'mts-kyc-prov',
    {
        props: {
            account_uid: {
                type: String
            }
        },
        delimiters: ['[[', ']]'],
        data() {
            return {
                loading: false,
                link_ttl: 180,
                error_msg: null,
                result_kyc_url: null
            }
        },
        methods: {
            generate_link(){
                console.log(this.account_uid);
                this.loading = true;
                this.error_msg = null;
                this.result_kyc_url = null;
                let self = this;

                let json = {
                    account_uid: this.account_uid,
                    link_ttl_minutes: this.link_ttl
                };
                const payload = JSON.stringify(json);
                const config = {
                    headers: {'Content-Type': 'application/json'}
                }
                axios
                    .post(
                        '/api/kyc/mts', payload, config
                    )
                    .then(
                        (response) => {
                            //mark_checked_rows();
                            console.log(response.data);
                            self.result_kyc_url = document.location.origin + '/kyc/' + response.data.id
                        }
                    ).catch(
                        (e) => {
                            self.error_msg = e.message || e.response.statusText
                        }
                    ).finally(
                        () => {
                            self.loading = false;
                        }
                    )
            },
            copy_link_to_clipboard(){
                navigator.clipboard.writeText(this.result_kyc_url);
                console.log('link copied to clipboard')
            }
        },
        template: `
            <div class="w-100 row p-3">
                <div class="form-group mb-2 col-4">
                    <p class="text-secondary">Время жизни ссылки (минуты)</p>
                </div>
                <div class="form-group mx-sm-3 mb-2 col-auto">
                  <input v-bind:disabled="result_kyc_url || loading" v-model="link_ttl" type="number" class="form-control" id="kyc_link_ttl" placeholder="минут...">
                </div>
                <button v-if="!loading && !result_kyc_url" @click.prevent="generate_link" type="submit" class="btn btn-primary mb-2 col-auto">Создать ссылку</button>
                <loader-circle v-if="loading"></loader-circle>
                <div v-if="error_msg" class="w-100 text-center">
                    <span class="text-danger">[[ error_msg ]]</span>
                </div>
                <div v-if="result_kyc_url" class="w-100 text-center">
                    <span class="text-secondary">Отправьте ссылку контрагенту для прохождения KYC</span>
                    <h5 @click.prevent="copy_link_to_clipboard" style="cursor:pointer;"  class="text-primary text-decoration-underline">[[ result_kyc_url ]] 
                        <button class="btn btn-secondary" style="margin-left: 2%;">Copy</button>
                    </h5>
                </div>
            </div>
        `
    }
)

Vue.component(
    'ClientsDb',
    {
        props: {
            header: {
                type: String,
                default: "Clients Db"
            },
        },
        delimiters: ['[[', ']]'],
        data() {
            return {
                data: [],
                data_map: {},
                loading: false,
                error_msg: null,
                labels: {
                    yes: 'Да',
                    no: 'Нет',
                    created: 'создано',
                    updated: 'обновлено',
                    record_empty: 'Запись не выбрана',
                    editing: 'Редактирование',
                    create_account: 'Создание аккаунта',
                    edit: 'edit',
                    add: 'Добавить',
                    refresh: 'Обновить',
                    kyc_verify: 'Провести верификацию личности',
                },
                details: null,
                table_: {
                    headers: [
                        {
                            label: '#',
                            sortable: true,
                        },
                        {
                            label: 'UID',
                            sortable: true,
                            type: "string"
                        },
                        {
                            label: 'Is Active',
                            sortable: false
                        },
                        {
                            label: 'Permissions',
                            sortable: false
                        },
                        {
                            label: 'Name',
                            sortable: true,
                            type: "string"
                        },
                        {
                            label: 'Contacts',
                            sortable: true
                        },
                        {
                            label: 'Organization',
                            sortable: true
                        },
                        {
                            label: 'Verified',
                            sortable: true
                        },
                        {
                            label: 'Tools',
                            sortable: false
                        },
                    ],
                    rows: [

                    ]
                },
                verify_modal: {
                    show: false,
                    account_uid: null,
                    name: null
                },
                edit_modal: {
                    show: false,
                    account_uid: null,
                    name: null,
                    portfolio: null,
                    active_tab: 0,
                    is_merchant: null
                },
                create_modal: {
                   show: false,
                   portfolio: null,
                   step: 0,
                   case: null,
                   nickname: '',
                   error_msg: null,
                   loading: false,
                   fine: false,
                   result_kyc_url: null,
                   link_ttl: 180
                },
                window_height: null,
                table_rows_counter: 0,
                _has_root_permission: false
            }
        },
        computed: {
            table_rows(){
                let rows = [];
                const empty_txt = '';
                this.table_rows_counter += 1;

                for(let i=0; i<this.data.length; i++) {
                    let o = this.data[i];
                    const no = i + 1;
                    let perms = [];
                    for (let i=0; i<o.permissions.length; i++) {
                        perms.push({
                            label: o.permissions[i],
                            class: 'badge bg-primary m-1'
                        })
                    }
                    let name = null;
                    if (o.first_name || o.last_name) {
                        if (o.first_name) {
                            name = o.first_name || '' + ' ' + o.last_name || '';
                        }
                        else {
                            name = o.last_name;
                        }
                    }
                    let contacts = [];
                     if (o.phone) {
                        contacts.push(o.phone);
                    }
                    if (o.email) {
                        contacts.push(o.email);
                    }
                    if (o.telegram) {
                        contacts.push(o.telegram);
                    }


                    let r = {
                        id: o.uid,
                        cells: [
                            {
                                id: 'no',
                                text: no.toString(),
                            },
                            {
                                id: 'uid',
                                text: trim_long_string(o.uid, 18),
                                style: 'font-weight: bold;'
                            },
                            {
                                id: 'active',
                                text: o.is_active ? this.labels.yes : this.labels.no,
                                class: o.is_active ? 'text-success' : 'text-secondary',
                                style: 'font-weight: bold;'
                            },
                            {
                                id: 'perm',
                                text: null,
                                badges: perms
                            },
                            {
                                id: 'name',
                                text: name ? name : empty_txt,
                                class: name ? '' : 'text-secondary'
                            },
                            {
                                id: 'contacts',
                                text: contacts.join('\n'),
                                style: 'white-space: pre-wrap;',
                            },
                            {
                                id: 'org',
                                text: o.is_organization ? this.labels.yes : this.labels.no,
                                class: o.is_organization ? 'text-success' : 'text-secondary',
                                style: 'font-weight: bold;'
                            },
                            {
                                id: 'verify',
                                text: null,
                                buttons: [
                                    {
                                        id: 'verify',
                                        label: o.is_verified ? this.labels.yes : this.labels.no,
                                        class: o.is_verified ? 'btn btn-sm btn-success' : 'btn btn-sm btn-danger'
                                    }
                                ]
                            },
                            {
                                id: 'tools',
                                text: null,
                                buttons: [
                                    {
                                        id: 'edit',
                                        label: this.labels.edit,
                                        class: 'btn btn-sm btn-secondary'
                                    }
                                ]
                            }
                        ]
                    }
                    rows.push(r);
                }
                return rows;
            },
            is_success() {
                return this.data.length > 0 && this.error_msg === null;
            }
        },
        mounted () {
            this.refresh();
            const cur_user = current_user();
            if (cur_user) {
                this._has_root_permission = cur_user.permissions.indexOf('root') >= 0;
            }
        },
        updated(){
            this.window_height = window.innerHeight;
        },
        methods: {
            refresh() {
                let self = this;
                self.loading = true;
                self.error_msg = null;
                self.details = null;
                console.log('Refresh Account Table');
                axios
                    .get('/api/accounts')
                    .then(
                        (response) => {
                            self.data = response.data;
                            self.rebuild_data_map();
                            if (self.$refs.table) {
                                self.$refs.table.refresh(self.table_rows);
                            }
                            //console.log(self.data_map);
                        }
                    ).catch(
                        (e) => {
                           self.error_msg = e.message || e.response.statusText
                        }
                    ).finally(
                        () => {
                            self.loading = false;
                        }
                    )
            },
            update_single_account(uid) {
                console.log('Refresh Singled Account ' + uid);
                let self = this;
                axios
                    .get('/api/accounts/' + uid)
                    .then(
                        (response) => {
                            console.log(response.data);
                            self.refresh();
                        }
                    ).catch(
                        (e) => {
                           self.error_msg = e.message || e.response.statusText
                        }
                    ).finally(
                        () => {
                            self.loading = false;
                        }
                    )
            },
            row_cell_click(id, row_index, col_index, uid) {
                const o = this.data_map[uid];
                if (o) {
                    let tab = 0;
                    if (this.details) {
                        tab = this.details.tab;
                    }
                    this.details = {
                        uid: o.uid,
                        utc: o.utc,
                        portfolio: o.portfolio,
                        tab: tab
                    }
                }
            },
            row_btn_click(id, row_index, col_index, uid){
                console.log('btn click', id, row_index, col_index, uid);
                const row = this.data_map[uid];
                let account_name = '';

                console.log(row);

                if (row.name) {
                    const first_name = row.name.first_name || "";
                    const last_name = row.name.last_name || "";
                    if (first_name || last_name) {
                        account_name = first_name + ' ' + last_name;
                    }
                    else {
                        account_name = row.uid;
                    }
                }

                if (id === 'verify') {
                    this.verify_modal.account_uid = row.uid;
                    this.verify_modal.name = account_name;
                    this.verify_modal.show = true;
                }
                else if (id === 'edit'){
                    this.edit_modal.account_uid = row.uid;
                    this.edit_modal.name = account_name;
                    this.edit_modal.show = true;
                    this.edit_modal.portfolio = JSON.parse(JSON.stringify(row.portfolio));
                    this.edit_modal.active_tab = 0;
                    this.edit_modal.is_merchant = this.edit_modal.portfolio.permissions.indexOf('merchant') >= 0;
                }
            },
            build_data_map_item(o, no) {
                let row = {
                    no: no+1,
                    uid: o.uid,
                    is_active: o.is_active,
                    permissions: o.permissions,
                    is_verified: o.is_verified,
                    is_organization: o.is_organization,
                    name: {
                        first_name: o.first_name || '',
                        last_name: o.last_name || ''
                    },
                    contacts: [

                    ],
                    utc: {
                        created_at: format_datetime_str(o.created_at),
                        updated_at: format_datetime_str(o.updated_at)
                    },
                    portfolio: o
                }
                if (o.phone) {
                    row.contacts.push({label: 'phone', value: o.phone});
                }
                if (o.email) {
                    row.contacts.push({label: 'email', value: o.email});
                }
                if (o.telegram) {
                    row.contacts.push({label: 'telegram', value: o.telegram});
                }
                return row;
            },
            rebuild_data_map() {
                let map = {};
                for(let i=0; i<this.data.length; i++) {
                    let o = this.data[i];
                    const row = this.build_data_map_item(o, i);
                    map[row.uid] = row;
                }
                this.data_map = map;
            },
            on_submit_account_form(){
                const self = this;
                const form = self.$refs.account_form;
                if (!form.validate()) {
                    return
                }
                form.disabled = true
                form.error_msg = null;
                form.success_msg = null;
                form.loading = true;

                const json = form.model;
                const payload = JSON.stringify(json);
                const config = {
                    headers: {'Content-Type': 'application/json'}
                }
                axios
                   .put(
                       '/api/accounts/' + self.edit_modal.account_uid,
                       payload, config
                   )
                   .then(
                       (response) => {
                           console.log(response.data);
                           form.success_msg = 'Данные успешно обновлены';
                           form.model = response.data;
                           self.update_single_account(self.edit_modal.account_uid)
                       }
                   ).catch(
                        (e) => {
                           form.error_msg = e.message || e.response.statusText;
                        }
                   ).finally(()=>{
                            form.disabled = false;
                            form.loading = false;
                        }
                   )

            },
            on_submit_merchant_form() {
                const self = this;
                const form = self.$refs.merchant_form;
                form.disabled = true
                form.error_msg = null;
                form.success_msg = null;
                form.loading = true;
                const json = form.model;
                const payload = JSON.stringify(json);
                const config = {
                    headers: {'Content-Type': 'application/json'}
                }
                axios
                   .post(
                       '/api/accounts/' + self.edit_modal.account_uid + '/update_merchant',
                       payload, config
                   )
                   .then(
                       (response) => {
                           console.log(response.data);
                           form.success_msg = 'Данные успешно обновлены';
                           form.model = response.data;
                           self.update_single_account(self.edit_modal.account_uid)
                       }
                   ).catch(
                        (e) => {
                           form.error_msg = e.message || e.response.statusText;
                        }
                   ).finally(()=>{
                            form.disabled = false;
                            form.loading = false;
                        }
                   )
            },
            on_submit_admin_form() {
                const self = this;
                const form = self.$refs.admin_form;
                form.disabled = true
                form.error_msg = null;
                form.success_msg = null;
                form.loading = true;
                const json = form.model;
                const payload = JSON.stringify(json);
                const config = {
                    headers: {'Content-Type': 'application/json'}
                }
                axios
                   .post(
                       '/api/accounts/' + self.edit_modal.account_uid + '/admin',
                       payload, config
                   )
                   .then(
                       (response) => {
                           console.log(response.data);
                           form.success_msg = 'Данные успешно обновлены';
                           form.model = response.data;
                           self.update_single_account(self.edit_modal.account_uid)
                       }
                   ).catch(
                        (e) => {
                           form.error_msg = gently_extract_error_msg(e);
                        }
                   ).finally(()=>{
                            form.disabled = false;
                            form.loading = false;
                        }
                   )
            },
            create_account(){
                this.create_modal.portfolio = null;
                this.create_modal.step = 0;
                this.create_modal.case = 'manual';
                this.create_modal.show = true;
                this.create_modal.nickname = '';
                this.create_modal.error_msg = null;
                this.create_modal.loading = false;
                this.create_modal.fine = false;
            },
            finish_create_account(){
                this.create_modal.show = false;
                this.refresh();
            },
            on_create_account_radio_manual_click(){
                this.$refs.radio_create_account_manual.checked = true;
                this.$refs.radio_create_account_link.checked = false;
            },
            on_create_account_radio_link_click(){
                this.$refs.radio_create_account_manual.checked = false;
                this.$refs.radio_create_account_link.checked = true;
            },
            on_create_account_prev(){
                this.create_modal.step -= 1;
                if (this.create_modal.step === 0) {
                    const self = this;
                    setTimeout(()=>{
                        self.$refs.radio_create_account_manual.checked = this.create_modal.case === 'manual';
                        self.$refs.radio_create_account_link.checked = this.create_modal.case === 'link';
                    }, 0);
                }
                this.create_modal.loading = false;
                this.create_modal.error_msg = null;
            },
            copy_reglink_to_clipboard(){
                navigator.clipboard.writeText(this.create_modal.result_kyc_url);
                console.log('link copied to clipboard')
            },
            on_create_account_next(){
                const self = this;
                if (this.create_modal.step === 0) {
                    const case_manual = this.$refs.radio_create_account_manual.checked;
                    const case_link = this.$refs.radio_create_account_link.checked;
                    this.create_modal.case = case_manual ? 'manual' : 'link';
                    self.create_modal.step += 1;
                    return
                }
                if (this.create_modal.case === 'manual') {
                    // step 1
                    if (this.create_modal.step === 1) {
                        if (!this.create_modal.nickname) {
                            self.create_modal.error_msg = 'Не может быть пустым';
                            return;
                        }
                        self.create_modal.loading = true;
                        axios
                            .get(
                                '/api/accounts/' + this.create_modal.nickname
                            )
                            .then(
                                (response) => {
                                    self.create_modal.error_msg = 'Аккаунт уже существует'
                                }
                            ).catch(
                            (e) => {
                                if (e.response.status === 404) {
                                    self.create_modal.step += 1;
                                } else {
                                    self.create_modal.error_msg = gently_extract_error_msg(e);
                                }
                            }
                        ).finally(() => {
                                self.create_modal.loading = false;
                            }
                        )
                    }
                    // step 2
                    else if (this.create_modal.step === 2) {
                        const form = this.$refs.create_account_form;
                        const ok = form.validate();
                        if (ok) {
                            form.set_loading(true);
                            form.disabled = true;
                            axios
                                .post(
                                    '/api/accounts/update_or_create?uid=' + this.create_modal.nickname,
                                    JSON.stringify(form.model),
                                    {
                                        headers: {'Content-Type': 'application/json'}
                                    }
                                )
                                .then(
                                    (response) => {
                                        self.create_modal.step += 1;
                                        self.create_modal.fine = true
                                    }
                                ).catch(
                                (e) => {
                                    form.error_msg = gently_extract_error_msg(e);
                                }
                            ).finally(() => {
                                    form.disabled = false;
                                    form.loading = false;
                                }
                            )
                        }
                    }
                }
                else if (this.create_modal.case === 'link') {
                    // step 1
                    if (this.create_modal.step === 1) {
                        self.create_modal.loading = true;
                        axios
                            .post(
                                '/api/kyc/mts/create_registration_link',
                                JSON.stringify({
                                    account_uid: this.create_modal.nickname,
                                    link_ttl_minutes: this.create_modal.link_ttl
                                }),
                                {
                                    headers: {'Content-Type': 'application/json'}
                                }
                            )
                            .then(
                                (response) => {
                                    //mark_checked_rows();
                                    console.log(response.data);
                                    self.create_modal.result_kyc_url = document.location.origin + '/register/' + response.data.id;
                                    self.create_modal.step += 1;
                                    self.create_modal.fine = true
                                }
                            ).catch(
                                (e) => {
                                    self.create_modal.error_msg = gently_extract_error_msg(e);
                                }
                            ).finally(
                                () => {
                                    self.create_modal.loading = false;
                                }
                            )
                    }
                }
            }
        },
        template: `
            <div class="w-100 row">
                <!-- Modal KYC form -->
                <modal-window v-if="verify_modal.show" >
                    <div slot="header" class="w-100">
                        <h3>[[ labels.kyc_verify ]]
                            <button class="btn btn-danger" @click="verify_modal.show = false" style="float: right;">
                                Close
                            </button>
                        </h3>
                    </div>
                    <div slot="body" class="w-100" style="overflow: auto;">
                        <p class="text-secondary">
                          Для пользователя <b class="text-primary">[[ verify_modal.name ]]</b> создайте ссылку для прохождения верификации.
                          После успешного завершения у пользователя обновится раздел KYC.
                        </p>
                        <mts-kyc-prov
                            :account_uid="verify_modal.account_uid"
                        ></mts-kyc-prov>
                    </div>
                    <div slot="footer" class="w-100 text-center">
                        
                    </div>
                </modal-window>
                <!-- Modal KYC form -->
                <!-- Modal Edit form -->
                <modal-window v-if="edit_modal.show" >
                    <div slot="header" class="w-100">
                        <h3>[[ labels.editing ]]
                            <button class="btn btn-danger" @click="edit_modal.show = false" style="float: right;">
                                Close
                            </button>
                        </h3>
                    </div>
                    <div slot="body" class="w-100 border-bottom border-top border-dark border-opacity-10" 
                        style="overflow-x: hidden; overflow-y: auto;" 
                        v-bind:style="{'max-height': 4*window_height/5 + 'px'}"
                    >
                        <p class="text-secondary">
                          Редактирование аккаунта <b class="text-primary">[[ edit_modal.name ]]</b>.
                        </p>
                        <nav class="nav nav-pills flex-column flex-sm-row border-bottom border-primary border-opacity-50">
                          <a 
                            v-bind:class="{active: edit_modal.active_tab === 0}"
                            @click.prevent="edit_modal.active_tab = 0" 
                            class="flex-sm-fill text-sm-center nav-link" aria-current="page" href=""
                          >
                            Аккаунт
                          </a>
                          <a 
                            v-bind:class="{active: edit_modal.active_tab === 1}"
                            @click.prevent="edit_modal.active_tab = 1" 
                            class="flex-sm-fill text-sm-center nav-link" aria-current="page" href=""
                          >
                            Авторизация
                          </a>
                          <a 
                            v-bind:class="{disabled: !edit_modal.is_merchant, active: edit_modal.active_tab === 2}" 
                            @click.prevent="edit_modal.active_tab = 2"
                            class="flex-sm-fill text-sm-center nav-link" href=""
                          >
                            Мерчант
                          </a>
                          <a 
                            v-bind:class="{active: edit_modal.active_tab === 3}" 
                            @click.prevent="edit_modal.active_tab = 3"
                            class="flex-sm-fill text-sm-center nav-link" href=""
                          >
                            Admin
                          </a>
                        </nav>
                        <div class="">
                            <account-fields-form
                                ref="account_form"
                                v-if="edit_modal.active_tab === 0"
                                :initial="edit_modal.portfolio"
                                @on_submit="on_submit_account_form"
                            ></account-fields-form>
                            <auth-fields-form
                                ref="auth_form"
                                v-if="edit_modal.active_tab === 1"
                                :account_uid="edit_modal.portfolio.uid"
                            ></auth-fields-form>
                            <merchant-fields-form
                                ref="merchant_form"
                                v-if="edit_modal.active_tab === 2"
                                :initial="edit_modal.portfolio.merchant_meta"
                                @on_submit="on_submit_merchant_form"
                            >
                            </merchant-fields-form>
                            <admin-fields-form
                                ref="admin_form"
                                v-if="edit_modal.active_tab === 3"
                                :initial="edit_modal.portfolio"
                                :has_root_permission="_has_root_permission"
                                @on_submit="on_submit_admin_form"
                            ></admin-fields-form>
                        </div>
                    </div>
                    <div slot="footer" class="w-100 text-center">
                        
                    </div>
                </modal-window>
                <!-- Modal edit form -->
                <!-- Modal create account form -->
                <modal-window v-if="create_modal.show" >
                    <div slot="header" class="w-100">
                        <h3>[[ labels.create_account ]]
                            <button class="btn btn-danger" @click="finish_create_account" style="float: right;">
                                Close
                            </button>
                        </h3>
                    </div>
                    <div slot="body" class="w-100 border-bottom border-top border-dark border-opacity-10" 
                        style="overflow-x: hidden; overflow-y: auto;" 
                        v-bind:style="{'max-height': 4*window_height/5 + 'px'}"
                    >
                       <div class="row" style="margin-top:5%;margin-bottom:5%;">
                            <div class="col">
                                <button 
                                    v-if="!create_modal.fine"
                                    @click.prevent="on_create_account_prev"
                                    class="btn btn-primary"
                                    v-bind:disabled="create_modal.step == 0 || create_modal.loading"
                                    style="position:absolute;"
                                >
                                    &larr; назад
                                </button>
                            </div>
                            <div class="col-auto">
                                <!--- Step-0 -->
                                <div v-if="create_modal.step === 0">
                                    <div class="form-check">
                                      <input 
                                        @click="on_create_account_radio_manual_click" 
                                        ref="radio_create_account_manual" 
                                        checked class="form-check-input" 
                                        type="radio" id="create.account.manual" 
                                        value="manual"
                                      >
                                      <label class="form-check-label" for="create.account.manual">
                                        Вручную
                                      </label>
                                    </div>
                                    <div class="form-check">
                                      <input 
                                        @click="on_create_account_radio_link_click"
                                        ref="radio_create_account_link" 
                                        class="form-check-input" 
                                        type="radio" id="create.account.link" 
                                        value="link"
                                      >
                                      <label class="form-check-label" for="create.account.link">
                                        Сформировать персональную ссылку
                                      </label>
                                    </div>
                                </div>
                                <!------>
                                <!--- Case manual -->
                                <div v-if="create_modal.case === 'manual'">
                                    <!--- Step-1 -->
                                    <div v-if="create_modal.step === 1">
                                        <label for="nickname" class="form-label">Nickname</label>
                                        <input v-model="create_modal.nickname" type="text" class="form-control" id="nickname">
                                        <p class="text-danger">[[ create_modal.error_msg ]]</p>
                                        <loader-circle 
                                            v-if="create_modal.loading"
                                            style="max-height:40px;"
                                        >
                                        </loader-circle>
                                    </div>
                                    <!--- Step-2 -->
                                    <div v-if="create_modal.step === 2">
                                        <account-fields-form
                                            ref="create_account_form"
                                            :initial="{}"
                                            :submit_enable="false"
                                        ></account-fields-form>
                                    </div>
                                    <!--- Step-3 -->
                                    <div class="text-center" v-if="create_modal.step === 3">
                                        <div class="alert alert-success">
                                            Аккаунт [[ create_modal.nickname ]] успешно создан
                                        </div>
                                        <button @click.prevent="finish_create_account" class="btn btn-success">
                                            Закрыть
                                        </button>
                                    </div>
                                </div>
                                <!----->
                                <!--- Case link -->
                                <div v-if="create_modal.case === 'link'">
                                    <!--- Step-1 -->
                                    <div v-if="create_modal.step === 1">
                                        <label for="nickname" class="form-label">Nickname</label>
                                        <input v-model="create_modal.nickname" type="text" class="form-control" id="nickname" placeholder="Необязательно">
                                        <label for="link_ttl" class="form-label">Время жизни ссылки (минуты)</label>
                                        <input v-model="create_modal.link_ttl" type="text" class="form-control" id="link_ttl">
                                        
                                        <p class="text-danger">[[ create_modal.error_msg ]]</p>
                                        <loader-circle 
                                            v-if="create_modal.loading"
                                            style="max-height:40px;"
                                        >
                                        </loader-circle>
                                    </div>
                                    <!--- Step-2 -->
                                    <div class="text-center" v-if="create_modal.step === 2">
                                        <div class="alert alert-success">
                                            Ссылка на регистрацию [[ create_modal.nickname ]] успешно создана
                                        </div>
                                        <div v-if="create_modal.result_kyc_url" class="w-100 text-center">
                                            <span class="text-secondary">Отправьте ссылку для прохождения регистрации</span>
                                            <h5 @click.prevent="copy_reglink_to_clipboard" style="cursor:pointer;"  class="text-primary text-decoration-underline">
                                                [[ create_modal.result_kyc_url ]] 
                                                <button class="btn btn-secondary" style="margin-left: 2%;">Copy</button>
                                            </h5>
                                        </div>
                                        <button @click.prevent="finish_create_account" class="btn btn-success">
                                            Закрыть
                                        </button>
                                    </div>
                                </div>
                            </div>
                            <div class="col">
                                <button 
                                    v-if="!create_modal.fine"
                                    @click.prevent="on_create_account_next" 
                                    class="btn btn-primary" 
                                    style="float:right;position:absolute;right:5%;"
                                    v-bind:disabled="create_modal.loading"
                                >
                                    &rarr; далее
                                </button>
                            </div>
                       </div>
                    </div>
                    <div slot="footer" class="w-100 text-center">
                        
                    </div>
                </modal-window>
                <!-- Modal create account form -->
                
                <div v-if="error_msg" class="alert alert-danger text-center">
                    <p>[[ error_msg ]]</p>
                </div>
                <div v-if="is_success" class="col-sm-8 card">
                    <div class="card-body">
                        <div>
                            <button @click.prevent="refresh" class="btn btn-primary btn-sm" v-bind:title="labels.refresh">
                                 <i class="fa-solid fa-rotate"></i>
                                 [[ labels.refresh ]]
                            </button>
                            <button @click.prevent="create_account" type="button" class="btn btn-success btn-sm">
                                   <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-plus-circle-fill" viewBox="0 0 16 16">
                                        <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0M8.5 4.5a.5.5 0 0 0-1 0v3h-3a.5.5 0 0 0 0 1h3v3a.5.5 0 0 0 1 0v-3h3a.5.5 0 0 0 0-1h-3z"></path>
                                   </svg>
                               [[ labels.add ]]
                            </button>
                            <loader v-if="loading === true" style="position:absolute;"></loader>
                        </div>
                        <data-table
                            ref="table"
                            style="text-align: left;"
                            :headers="table_.headers"
                            :rows="table_rows"
                            :searchable="true"
                            @click_btn="row_btn_click"
                            @click_cell="row_cell_click"
                        ></data-table>
                    </div>
                </div>
                <div v-if="is_success" class="col-sm-4">
                    <div class="card mt-4">
                        <div class="card-header">
                            <h6 class="card-title">Details <span class="text-primary">[[details ? details.uid: '']]</span></h6>
                        </div>
                        <div class="card-body">
                            <div class="alert alert-danger text-center" v-if="!details">
                                [[ labels.record_empty ]]
                            </div>
                            <div class="w-100" v-if="details">
                                <div class="row w-100 p-2">
                                    <div class="col">
                                        <span class="text-secondary">[[ labels.updated ]]:</span>
                                        <br/>
                                        <span class="text-primary">[[ details.utc.updated_at ]]</span>
                                    </div>
                                    <div class="col">
                                        <span class="text-secondary">[[ labels.created ]]:</span>
                                        <br/>
                                        <span class="text-primary">[[ details.utc.created_at ]]</span>
                                    </div>
                                </div>
                                <ul class="nav nav-tabs" id="myTab" role="tablist">
                                  <li class="nav-item">
                                    <a 
                                        @click.prevent="details.tab = 0"
                                        v-bind:class="{'active': details.tab === 0}"
                                        class="nav-link" href="#account" 
                                        role="tab" aria-controls="account" aria-selected="true"
                                    >Account</a>
                                  </li>
                                  <li class="nav-item">
                                    <a 
                                        @click.prevent="details.tab = 1"
                                        v-bind:class="{'active': details.tab === 1}"
                                        class="nav-link" href="#merchant" 
                                        role="tab" aria-controls="merchant" aria-selected="false"
                                    >Merchant</a>
                                  </li>
                                  <li class="nav-item">
                                    <a 
                                        @click.prevent="details.tab = 2"
                                        v-bind:class="{'active': details.tab === 2}"
                                        class="nav-link" href="#kyc" 
                                        role="tab" aria-controls="kyc" aria-selected="false"
                                    >KYC</a>
                                  </li>
                                </ul>
                                <div class="tab-content p-4 border border-light">
                                  <div 
                                        v-bind:class="{'active': details.tab === 0, 'show': details.tab === 0}"
                                        class="tab-pane fade" 
                                        role="tabpanel"
                                  >
                                    <account-info :account="details.portfolio"></account-info>
                                  </div>
                                  <div 
                                        v-bind:class="{'active': details.tab === 1, 'show': details.tab === 1}" 
                                        class="tab-pane fade" 
                                        role="tabpanel"
                                  >
                                    <merchant-info :merchant="details.portfolio.merchant_meta"></merchant-info>
                                  </div>
                                  <div 
                                        v-bind:class="{'active': details.tab === 2, 'show': details.tab === 2}" 
                                        class="tab-pane fade" 
                                        role="tabpanel"
                                  >
                                    <kyc-info 
                                        :account_uid="details.uid"
                                    ></kyc-info>
                                  </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `
    }
);

Vue.component(
    'ClientsCRM',
    {
        props: {
            header: {
                type: String,
                default: "Clients CRM"
            },
        },
        delimiters: ['[[', ']]'],
        template: `
            <div class="w-100 text-center">
                <div class="alert alert-danger">
                    <h4>Страница клиентов CRM не подключена</h4>
                    <p>Обратитесь к администратору сервиса за консультацией</p>
                </div>
            </div>
        `
    }
);

Vue.component(
    'Forms',
    {
        props: {
            header: {
                type: String,
                default: "Forms"
            },
        },
        delimiters: ['[[', ']]'],
        template: `
            <div class="w-100 text-center">
                <div class="alert alert-danger">
                    <h4>Страница редактирования форм инвойсов не активирована</h4>
                    <p>Обратитесь к администратору сервиса за консультацией</p>
                </div>
            </div>
        `
    }
);

Vue.component(
    'Markets',
    {
        props: {
            header: {
                type: String,
                default: "Рынки"
            },
        },
        delimiters: ['[[', ']]'],
        data(){
            return {
                data: null,
                error_msg: null,
                loading: false,
                table: {
                    headers: [
                        {label: 'Scope', sortable: true},
                        {label: 'Площадка', sortable: true},
                        {label: 'Курс', sortable: false},
                        {label: 'Клиент отдает', sortable: true},
                        {label: 'Клиент получает', sortable: true},
                        {label: 'UTC', sortable: true}
                    ],
                    rows: []
                },
                filters: []
            }
        },
        mounted(){
            this.refresh();
        },
        methods: {
            rebuild_filters(){
                let filters = [
                    {
                        label: 'Все',
                        value: 'all',
                        checked: true,
                        class: 'btn-primary',
                        single: true,
                    }
                ];
                let filters_ids = [];
                for (let i=0; i<this.data.length; i++) {
                    const o = this.data[i];
                    const filter_id = o.scope;
                    if (filters_ids.indexOf(filter_id) < 0) {
                        filters_ids.push(filter_id);
                        filters.push(
                            {
                                label: filter_id,
                                value: filter_id,
                                checked: false,
                                class: 'btn-primary',
                                single: false,
                            }
                        )
                    }
                }
                this.filters = filters;
            },
            rebuild_table_rows(){
                let rows = [];

                function format_utc(s) {
                    const parts = s.split('.');
                    return parts[0];
                }

                let avail_scopes = [];
                let all_scopes = false;
                for (let i=0; i<this.filters.length; i++) {
                    const flt = this.filters[i];
                    if (flt.value === 'all' && flt.checked) {
                        all_scopes = true;
                        break;
                    }
                    if (flt.checked) {
                        avail_scopes.push(flt.value);
                    }
                }

                for (let i=0; i<this.data.length; i++) {
                    const o = this.data[i];
                    if (!all_scopes) {
                        if (avail_scopes.indexOf(o.scope) < 0) {
                            continue;
                        }
                    }

                    let rate = o.rate > 1 ? o.rate : 1/o.rate;
                    rate = parseFloat(rate.toFixed(2));
                    let row = {
                        id: o.id,
                        cells: [
                            {
                                id: 'scope',
                                text: o.scope,
                                class: 'fw-bold'
                            },
                            {
                                id: 'engine',
                                text: o.engine
                            },
                            {
                                id: 'rate',
                                text: rate.toLocaleString(),
                                class: 'text-primary'
                            },
                            {
                                id: 'give',
                                text: o.give.symbol,
                                badges: [
                                    {
                                        label: o.give.method,
                                        class: 'badge bg-secondary',
                                        style: 'margin-left: 1%;'
                                    }
                                ]
                            },
                            {
                                id: 'get',
                                text: o.get.symbol,
                                badges: [
                                    {
                                        label: o.get.method,
                                        class: 'badge bg-secondary',
                                        style: 'margin-left: 1%;'
                                    }
                                ]
                            },
                            {
                                id: 'utc',
                                text: format_utc(o.utc[1])
                            }
                        ]
                    }
                    rows.push(row);
                }
                this.table.rows = rows;
                this.$refs.table.refresh(rows);
            },
            refresh() {
                const self = this;
                self.error_msg = null;
                self.loading = true;
                axios
                    .get('/api/ratios/external')
                    .then(
                        (response) => {
                            self.data = response.data;
                            self.rebuild_filters();
                            self.rebuild_table_rows();
                            //console.log(self.data)
                        }
                    ).finally(
                       response => (
                           self.loading = false
                       )
                    ).catch(
                        (e) => {
                            self.error_msg = gently_extract_error_msg(e)
                        }
                    )
            },
            on_filters_changed(){
                this.rebuild_table_rows();
            }
        },
        template: `
            <div class="w-100 text-center">
                <div v-if="error_msg" class="alert alert-danger">
                    <p>[[ error_msg ]]</p>
                </div>
                <div
                    class="card text-left"
                >
                    <div class="card-header">
                        <button 
                            @click.prevent="refresh()" 
                            class="btn btn-primary btn-sm" 
                            title="Обновить"
                            style="float:left;margin-right:3px;"
                        >
                            <i class="fa-solid fa-rotate"></i>
                        </button>
                        <h5 style="text-align: left;">Котировки на внешних рынках</h5>
                    </div>
                    <div class="card-body" style="text-align:left;">
                        <filters-block 
                            :items="filters"
                            @changed="on_filters_changed"
                        ></filters-block>
                        <data-table
                            ref="table"
                            style="text-align: left;"
                            :searchable="true"
                            :headers="table.headers"
                            :rows="table.rows"
                        ></data-table>
                        <loader-circle
                            v-if="loading"
                            style="position:absolute;top:10%;left:0;"
                        ></loader-circle>
                    </div>
                </div>
            </div>
        `
    }
);

Vue.component(
    'AdminCurrencies',
    {
        delimiters: ['[[', ']]'],
        data(){
            return {
                currencies: [],
                error_msg: null,
                loading: false,
                table: {
                    headers: [
                        {label: 'ID', sortable: true},
                        {label: 'Symbol', sortable: true},
                        {label: 'Icon', sortable: false},
                        {label: 'Type', sortable: true},
                        {label: 'Active', sortable: false},
                        {label: 'Платежи', sortable: false},
                        {label: 'Owner', sortable: false},
                        {label: 'Операции', sortable: false},
                    ],
                    rows: []
                },
                modal_edit: false,
                modal_delete: false,
                modal_loading: false,
                modal_error: null,
                modal_success: null,
                edit_model: {
                    id: null,
                    icon: null,
                    symbol: null,
                    is_fiat: null,
                    is_enabled: null,
                    payments_count: 0
                },
                delete_model: null,
                mode: 'edit' // edit, create
            }
        },
        mounted(){
            const icon_input = this.$refs.icon_file;
            const self = this;
            icon_input.addEventListener('change', (e) => {
                // Get a reference to the file
                const file = e.target.files[0];

                // Encode the file using the FileReader API
                const reader = new FileReader();
                reader.onloadend = () => {
                    //console.log(reader.result);
                    self.edit_model.icon = reader.result;
                };
                reader.readAsDataURL(file);
            });
            this.refresh();
        },
        methods: {
            rebuild_table_rows(){
                let rows = [];
                for (let i=0; i<this.currencies.length; i++) {
                    const o = this.currencies[i];
                    let cell_icon = {
                        id: 'icon',
                        text: ''
                    }
                    if (o.icon) {
                        cell_icon.icon = {
                            src: o.icon,
                            style: o.icon ? 'max-height: 25px;margin-left:4px;' : 'display:none;'
                        }
                    }

                    let row = {
                        id: o.id,
                        cells: [
                            {
                                id: 'id',
                                text: o.id.toString(),
                                class: 'fw-bold',

                            },
                            {
                                id: 'symbol',
                                text: o.symbol,
                                class: 'text-primary'
                            },
                            cell_icon,
                            {
                                id: 'type',
                                text: o.is_fiat ? 'Fiat' : 'Crypto',
                                class: 'badge bg-primary'
                            },
                            {
                                id: 'active',
                                text: o.is_enabled ? 'Да' : 'Нет',
                                class: o.is_enabled ? 'badge bg-success' : 'badge bg-danger'
                            },
                            {
                                id: 'payments',
                                text: o.payments_count.toString(),
                                class: !o.payments_count ? 'text-danger' : 'text-secondary'
                            },
                            {
                                id: 'owner',
                                text: o.owner_did,
                                class: 'text-primary'
                            },
                            {
                                text: '',
                                buttons: [
                                    {
                                        id: 'edit',
                                        label: 'Edit',
                                        class: 'btn btn-sm btn-primary',
                                        style: 'margin-left: 5%;'
                                    },
                                    {
                                        id: 'del',
                                        label: 'Delete',
                                        class: 'btn btn-sm btn-danger',
                                        style: 'margin-left: 1%;'
                                    }
                                ]
                            }
                        ]
                    }
                    rows.push(row);
                }
                this.table.rows = rows;
                this.$refs.table.refresh(rows);
            },
            refresh(){
                const self = this;
                self.loading = true;
                axios
                   .get('/api/exchange/currencies')
                   .then(
                       (response) => {
                           self.currencies = response.data;
                           console.log(response.data);
                           self.rebuild_table_rows();
                       }
                   ).catch(
                       (e) => {
                            self.error_msg = gently_extract_error_msg(e)
                       }
                   ).finally(
                       response => (
                           self.loading = false
                       )
                   )
            },
            row_btn_click(id, row_index, col_index, uid){
                if (id === 'edit') {
                    this.mode = 'edit';
                    for (let i = 0; i < this.currencies.length; i++) {
                        const cur = this.currencies[i];
                        if (cur.id == uid) {
                            for (let attr in cur) {
                                this.edit_model[attr] = cur[attr];
                            }
                            this.modal_edit = true;
                            this.modal_success = null;
                            this.modal_error = null;
                            this.modal_loading = false;
                            return;
                        }
                    }
                    console.log('Не найдена валюта')
                }
                else if (id === 'del') {
                    this.delete_model = null;
                    for (let i = 0; i < this.currencies.length; i++) {
                        const cur = this.currencies[i];
                        if (cur.id == uid) {
                            if (cur.payments_count > 0) {
                                this.modal_error = 'Вы не можете удалить валюту, которая указана в платежном методе'
                            }
                            else {
                                this.modal_error = null;
                            }
                            this.delete_model = cur;
                            this.modal_delete = true;
                            this.modal_loading = false;
                            return;
                        }
                    }
                    console.log('Не найдена валюта при удалении')
                }
            },
            create_new(){
                this.mode = 'create';
                this.edit_model = {
                    id: null,
                    icon: null,
                    symbol: null,
                    is_fiat: true,
                    is_enabled: true,
                };
                this.modal_success = null;
                this.modal_error = null;
                this.modal_loading = false;
                this.modal_edit = true;
            },
            change_icon(){
                let input = this.$refs.icon_file;
                input.click();
                //console.log(input);
            },
            submit(){
                const self = this;
                self.modal_success = null;
                self.modal_error = null;
                self.modal_loading = true;

                const payload = JSON.stringify(self.edit_model);
                const config = {
                    headers: {'Content-Type': 'application/json'}
                }
                if (self.mode == 'edit') {
                    axios
                        .put(
                            '/api/exchange/currencies' + '/' + self.edit_model.id,
                            payload, config
                        )
                        .then(
                            (response) => {
                                self.modal_success = 'Данные успешно обновлены'
                                self.refresh();
                            }
                        ).catch(
                        (e) => {
                            self.modal_error = 'Ошибка';
                        }
                    ).finally(
                        response => (
                            self.modal_loading = false
                        )
                    )
                }
                else {
                    axios
                        .post(
                            '/api/exchange/currencies',
                            payload, config
                        )
                        .then(
                            (response) => {
                                self.modal_success = 'Новая валюта успешно создана'
                                self.refresh();
                            }
                        ).catch(
                        (e) => {
                            self.modal_error = 'Ошибка';
                        }
                    ).finally(
                        response => (
                            self.modal_loading = false
                        )
                    )
                }
            },
            submit_delete(){
                const self = this;
                axios
                    .delete(
                        '/api/exchange/currencies' + '/' + this.delete_model.id
                    )
                    .then(
                        (response) => {
                            self.refresh();
                            self.modal_delete = false;
                        }
                    ).catch(
                    (e) => {
                        self.modal_error = 'Ошибка';
                    }
                ).finally(
                    response => (
                        self.modal_loading = false
                    )
                )
            }
        },
        template: `
        <div class="w-100 text-left">
            <input ref="icon_file" type="file" style="display: none;">
        
            <modal-window v-if="modal_edit">
                <div slot="header" class="w-100">
                    <h3> 
                        <span v-if="mode == 'edit'">Редактор</span> 
                        <b v-if="mode == 'edit'">[[ edit_model.symbol ]]</b>
                        <span v-if="mode == 'create'">Добавление валюты</span>
                        <button class="btn btn-danger" @click="modal_edit = false" style="float: right;">
                            Close
                        </button>
                    </h3>
                </div>
                <div slot="body" class="w-100 text-center">
                    <div class="row w-100 border border-secondary border-opacity-10 p-3">
                        <div class="col-5 text-center">
                            <img 
                                v-if="edit_model.icon"
                                v-bind:src="edit_model.icon" style="max-height: 5rem;max-width:5rem;cursor: pointer;" 
                                title="Edit Icon"
                                @click.prevent="change_icon"
                            />
                            <a 
                                v-if="!edit_model.icon"
                                @click.prevent="change_icon" href=""
                            >
                                Установить иконку
                            </a>
                        </div>
                        <div class="col-5">
                            <div class="form-group row">
                                <label for="symbol" class="col-sm-2 col-form-label col-form-label-sm text-secondary">Symbol</label>
                                <div class="col-sm-4">
                                  <input v-bind:disabled="edit_model.payments_count > 0" v-model="edit_model.symbol" type="text" class="form-control form-control-sm" id="symbol" placeholder="symbol">
                                </div>
                            </div>
                            <div class="form-group row">
                                <div class="form-check col-sm-4">
                                    <input v-model="edit_model.is_fiat" class="form-check-input" type="checkbox" id="fiat">
                                    <label class="form-check-label" for="fiat">Fiat</label>
                                </div>
                            </div>
                            <div class="form-group row">
                                <div class="form-check col-sm-4">
                                    <input v-model="edit_model.is_enabled" class="form-check-input" type="checkbox" id="active">
                                    <label class="form-check-label" for="active">Active</label>
                                </div>
                            </div>
                            <div class="form-group row">
                                <label for="payments_count" class="col-sm-6 col-form-label col-form-label-sm text-secondary">Участвует в платежах</label>
                                <div class="col-sm-2">
                                  <input disabled="disabled" v-model="edit_model.payments_count" type="text" class="form-control form-control-sm" id="payments_count">
                                </div>
                               
                            </div>
                        </div>
                    </div>
                    <div class="w-100 text-center p-1">
                        <p 
                            v-if="modal_error" 
                            class="alert alert-danger"
                        >[[ modal_error ]]</p>
                        <p
                            v-if="modal_success" 
                            class="alert alert-success"
                        >[[modal_success]]</p>
                        <button 
                            v-if="!modal_loading && !modal_error" 
                            @click.prevent="submit()" 
                            class="btn btn-primary m-3"
                        >Submit</button>
                        <loader-circle
                            v-if="modal_loading"
                        ></loader-circle>
                    </div>
                </div>
                <div slot="footer" class="w-100 text-center">
                </div>
            </modal-window>
            
            <modal-window v-if="modal_delete">
                <div slot="header" class="w-100">
                    <h3> 
                        <span>Удаление</span> 
                        <b>[[ delete_model.symbol ]]</b>
                        <button class="btn btn-danger" @click="modal_delete = false" style="float: right;">
                            Close
                        </button>
                    </h3>
                </div>
                <div slot="body" class="w-100 text-center">
                    <div class="w-100 text-center">
                        <p class="alert alert-primary">
                            Вы уверены, что хотите удалить запись Валюты?
                        </p>
                        <p 
                            v-if="modal_error" 
                            class="alert alert-danger"
                        >[[ modal_error ]]</p>
                        <div class="row">
                            <div class="col"></div>
                            <button v-if="!modal_loading && !modal_error" @click.prevent="modal_delete=false" class="btn btn-secondary col-2 m-2">Отмена</button>
                            <button v-if="!modal_loading && !modal_error" @click.prevent="submit_delete" class="btn btn-danger col-2 m-2">Да</button>
                            <div class="col"></div>
                        </div>
                        <loader-circle
                            v-if="modal_loading"
                        ></loader-circle>
                    </div>
                </div>
                <div slot="footer" class="w-100 text-center">
                </div>
            </modal-window>
                
                
            <div v-if="error_msg" class="alert alert-danger text-center">
                <p>[[ error_msg ]]</p>
            </div>
            <div class="card text-left">
                <div class="card-header">
                    <button 
                        @click.prevent="refresh()" 
                        class="btn btn-primary btn-sm" 
                        title="Обновить"
                        style="float:left;margin-right:3px;"
                    >
                        <i class="fa-solid fa-rotate"></i>
                    </button>
                    <h5 style="text-align: left;">Редактор валют</h5>
                </div>
                <div class="card-body" style="text-align:left;">
                    <div class="w-100 text-center">
                        <a @click.prevent="create_new" class="text-success" href="">
                          <svg style="height:100%;width:max-content;" xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-plus-square-dotted" viewBox="0 0 16 16">
                              <path d="M2.5 0q-.25 0-.487.048l.194.98A1.5 1.5 0 0 1 2.5 1h.458V0zm2.292 0h-.917v1h.917zm1.833 0h-.917v1h.917zm1.833 0h-.916v1h.916zm1.834 0h-.917v1h.917zm1.833 0h-.917v1h.917zM13.5 0h-.458v1h.458q.151 0 .293.029l.194-.981A2.5 2.5 0 0 0 13.5 0m2.079 1.11a2.5 2.5 0 0 0-.69-.689l-.556.831q.248.167.415.415l.83-.556zM1.11.421a2.5 2.5 0 0 0-.689.69l.831.556c.11-.164.251-.305.415-.415zM16 2.5q0-.25-.048-.487l-.98.194q.027.141.028.293v.458h1zM.048 2.013A2.5 2.5 0 0 0 0 2.5v.458h1V2.5q0-.151.029-.293zM0 3.875v.917h1v-.917zm16 .917v-.917h-1v.917zM0 5.708v.917h1v-.917zm16 .917v-.917h-1v.917zM0 7.542v.916h1v-.916zm15 .916h1v-.916h-1zM0 9.375v.917h1v-.917zm16 .917v-.917h-1v.917zm-16 .916v.917h1v-.917zm16 .917v-.917h-1v.917zm-16 .917v.458q0 .25.048.487l.98-.194A1.5 1.5 0 0 1 1 13.5v-.458zm16 .458v-.458h-1v.458q0 .151-.029.293l.981.194Q16 13.75 16 13.5M.421 14.89c.183.272.417.506.69.689l.556-.831a1.5 1.5 0 0 1-.415-.415zm14.469.689c.272-.183.506-.417.689-.69l-.831-.556c-.11.164-.251.305-.415.415l.556.83zm-12.877.373Q2.25 16 2.5 16h.458v-1H2.5q-.151 0-.293-.029zM13.5 16q.25 0 .487-.048l-.194-.98A1.5 1.5 0 0 1 13.5 15h-.458v1zm-9.625 0h.917v-1h-.917zm1.833 0h.917v-1h-.917zm1.834-1v1h.916v-1zm1.833 1h.917v-1h-.917zm1.833 0h.917v-1h-.917zM8.5 4.5a.5.5 0 0 0-1 0v3h-3a.5.5 0 0 0 0 1h3v3a.5.5 0 0 0 1 0v-3h3a.5.5 0 0 0 0-1h-3z"/>
                          </svg>
                          <span class="margin-left:3%;">Добавить валюту</span> 
                        </a>
                    </div>
                    <data-table
                        ref="table"
                        style="text-align: left;"
                        :searchable="true"
                        :headers="table.headers"
                        :rows="table.rows"
                        @click_btn="row_btn_click"
                    ></data-table>
                    <loader-circle
                        v-if="loading"
                        style="position:absolute;top:10%;left:0;"
                    ></loader-circle>
                </div>
            </div>
        </div>
        `
    }
);

Vue.component(
    'AdminMethods',
    {
        delimiters: ['[[', ']]'],
        data(){
            return {
                error_msg: null,
                loading_costs: false,
                costs: [],
                cost_create_mode: false,
                loading_methods: false,
                table: {
                    headers: [
                        {
                            label: 'Bestchange Code',
                            sortable: true,
                        },
                        {
                            label: 'Method uid',
                            sortable: true,
                            type: "string"
                        },
                        {
                            label: 'Cur',
                            sortable: false
                        },
                        {
                            label: 'Icon',
                            sortable: false
                        },
                        {
                            label: 'User-friendly Name',
                            sortable: true,
                            type: "string"
                        },
                        {
                            label: 'Sub',
                            sortable: false
                        }
                    ],
                    rows: []
                },
                editing_row: null,
                show_edit_modal: false,
                methods_map: {},
                modal_mode: 'edit', // edit | create,
                method_under_edit: {},
                active_curs: []
            }
        },
        mounted(){
            this.refresh();
        },
        updated(){
            /*
            $( "#cur-autocomplete" ).autocomplete({
                source: "/api/autocomplete/active-curs",
                autoFocus: true,
                classes: {
                    "ui-autocomplete": "list-group-item list-group-item-light"
                }
            });*/
        },
        methods: {
            refresh(target = 'all'){
                load_costs = target === 'costs' || target === 'all';
                load_payments = target === 'payments' || target === 'all';
                load_active_curs = target === 'curs' || target === 'all';
                const self = this;
                if (load_costs) {
                    self.loading_costs = true;
                    axios
                        .get('/api/exchange/costs')
                        .then(
                            (response) => {
                                //console.log(response.data);
                                let new_costs = [];
                                for (let i=0; i<response.data.length; i++) {
                                    let c = response.data[i];
                                    c.editing = false;
                                    c.loading = false;
                                    c.error = null;
                                    new_costs.push(c);
                                }
                                self.costs = new_costs;
                            }
                        ).finally(
                            response => (
                                self.loading_costs = false
                            )
                        )
                }
                if (load_payments) {
                    self.loading_methods = true;
                    axios
                        .get('/api/exchange/payments')
                        .then(
                            (response) => {
                                //console.log(response.data);
                                let rows = [];
                                self.methods_map = {};
                                for (let i=0; i<response.data.length; i++) {
                                    let o = response.data[i];
                                    self.methods_map[o.code] = o;
                                    let cell_icon = {
                                        id: 'icon',
                                        text: ''
                                    }
                                    if (o.icon) {
                                        cell_icon.icon = {
                                            src: o.icon,
                                            style: o.icon ? 'max-height: 25px;margin-left:4px;' : 'display:none;'
                                        }
                                    }
                                    let row = {
                                        id: o.code,
                                        cells: [
                                            {
                                                id: 'code',
                                                text: o.code,
                                                class: 'fw-bold',
                
                                            },
                                            {
                                                id: 'method',
                                                text: o.method,
                                                class: 'text-primary'
                                            },
                                            {
                                                id: 'cur',
                                                text: o.cur,
                                                class: 'text-primary'
                                            },
                                            cell_icon,
                                            {
                                                id: 'user_friendly_name',
                                                text: o.name,
                                            },
                                            {
                                                id: 'sub',
                                                text: o.sub,
                                                class: 'badge bg-primary'
                                            }
                                        ]
                                    }
                                    rows.push(row);
                                }
                                this.$refs.table.refresh(rows);
                            }
                        ).finally(
                            (response) => {
                                self.loading_methods = false;
                            }
                        )
                }
                if (load_active_curs) {
                    axios
                        .get('/api/autocomplete/active-curs')
                        .then(
                            (response) => {
                                //console.log(response.data);
                                self.active_curs = response.data;
                            }
                        )
                }
            },
            create_cost(cost){
                if (!cost.id) {
                    cost.error = 'ID пуст';
                    return;
                }
                cost.loading = true;
                const payload = JSON.stringify(
                    {
                        id: cost.id,
                        cost: parseFloat(cost.cost),
                        is_percents: cost.is_percents,
                        cur: cost.cur
                    }
                );
                const config = {
                    headers: {'Content-Type': 'application/json'}
                }
                cost.loading = true;
                cost.error = null
                const self = this;
                axios
                    .post(
                        '/api/exchange/costs',
                        payload, config
                    )
                    .then(
                        (response) => {
                            this.cost_create_mode = false;
                            self.refresh('costs');
                        }
                    ).catch(
                        (e) => {
                            cost.error = gently_extract_error_msg(e);
                        }
                    ).finally(
                        response => (
                            cost.loading = false
                        )
                    )
            },
            update_cost(id) {
                let c = null;
                for (let i=0; i<this.costs.length; i++) {
                    c = this.costs[i];
                    if (c.id === id) {
                        break;
                    }
                }
                if (c === null) {
                    return;
                }

                const payload = JSON.stringify(
                    {
                        cost: parseFloat(c.cost),
                        is_percents: c.is_percents,
                        cur: c.cur
                    }
                );
                const config = {
                    headers: {'Content-Type': 'application/json'}
                }
                c.loading = true;
                c.error = null
                axios
                    .put(
                        '/api/exchange/costs/' + id,
                        payload, config
                    )
                    .then(
                        (response) => {
                            c.cost = response.data.cost;
                            c.is_percents = response.data.is_percents;
                            c.cur = response.data.cur;
                        }
                    ).catch(
                        (e) => {
                            c.error = gently_extract_error_msg(e);
                        }
                    ).finally(
                        response => (
                            c.loading = false
                        )
                    )
            },
            delete_cost(id) {
                let c = null;
                for (let i=0; i<this.costs.length; i++) {
                    c = this.costs[i];
                    if (c.id === id) {
                        break;
                    }
                }
                if (c === null) {
                    return;
                }
                c.loading = true;
                c.error = null
                const self = this;
                axios
                    .delete(
                        '/api/exchange/costs/' + id
                    )
                    .then(
                        (response) => {
                            self.refresh('costs');
                        }
                    ).catch(
                        (e) => {
                            c.error = gently_extract_error_msg(e);
                        }
                    ).finally(
                        response => (
                            c.loading = false
                        )
                    )
            },
            make_cost_create_mode(on){
                if (on) {
                    let new_cost = {
                        creating: true,
                        loading: false,
                        editing: true,
                        error: null,
                        cost: 0,
                        is_percents: false,
                        cur: 'USD'
                    }
                    this.costs.push(new_cost);
                }
                else {
                    let new_costs = [];
                    for (let i=0; i<this.costs.length; i++) {
                        const c = this.costs[i];
                        if (!c.creating) {
                            new_costs.push(c);
                        }
                    }
                    this.costs = new_costs;
                }
                this.cost_create_mode = on;
            },
            cancel_cost_item(cost) {
                if (cost.creating) {
                    this.make_cost_create_mode(false);
                }
                else {
                    dump = cost._dump;
                    if (dump) {
                        cost.cost = dump.cost;
                        cost.cur = dump.cur;
                        cost.is_percents = dump.is_percents;
                        cost._dump = null;
                    }
                    cost.editing = false;
                }
            },
            edit_cost_item(cost, flag, commit=false){
                if (cost.editing === flag) {
                    return;
                }
                cost.editing = flag;
                if (flag) {
                    cost._dump = {
                        cost: cost.cost,
                        cur: cost.cur,
                        is_percents: cost.is_percents
                    }
                    for (let i=0; i<this.costs.length; i++) {
                        let c = this.costs[i];
                        if (c.id !== cost.id) {
                            this.cancel_cost_item(c);
                        }
                    }
                }
                else {
                    cost._dump = null;
                    if (commit) {
                        this.update_cost(cost.id);
                    }
                }
                
            },
            on_select_row(index, code){
                this.modal_mode = 'edit';
                for (let key in this.methods_map[code]) {
                    const value = this.methods_map[code][key];
                    this.method_under_edit[key] = value
                }
                //console.log(this.method_under_edit);
                this.show_edit_modal = true;
            }
        },
        template: `
        <div class="w-100">
            <div v-if="error_msg" class="alert alert-danger text-center">
                <p>[[ error_msg ]]</p>
            </div>

            <modal-window v-if="show_edit_modal" @close="show_edit_modal = false">
                <div slot="header" class="w-100">
                    <h3>
                        <span v-if="modal_mode === 'edit'">Edit Method <b class="text-primary">[[ method_under_edit.code ]]</b></span>
                        <span v-if="modal_mode === 'create'">Create Method</span>
                        <button class="btn btn-danger" @click="show_edit_modal = false" style="float: right;">
                            Close
                        </button>
                    </h3>
                </div>
                <div slot="body" class="w-100" >
                    <div class="input-group input-group-sm mb-3">
                        <span class="input-group-text">Code</span>
                        <input readonly="readonly" v-model="method_under_edit.code" type="text" class="form-control">
                    </div>
                    <div class="input-group input-group-sm mb-3">
                        <span class="input-group-text">Method UID</span>
                        <input v-model="method_under_edit.method" type="text" class="form-control">
                        <span class="input-group-text">Currency</span>
                        <select class="form-select" v-model="method_under_edit.cur">
                            <option v-for="cur in active_curs">[[ cur.value ]]</option>
                        </select>
                    </div>
                    <div class="input-group input-group-sm mb-3">
                        <span class="input-group-text">User-Friendly Name</span>
                        <input v-model="method_under_edit.name" type="text" class="form-control">
                        <span class="input-group-text">Sub</span>
                        <select class="form-select" v-model="method_under_edit.cur">
                            <option v-for="cur in active_curs">[[ cur.value ]]</option>
                        </select>
                    </div>
                </div>
                <div slot="footer" class="w-100 text-center"></div>
            </modal-window>

            <div class="card text-left">
                <div class="card-header">
                    <button 
                        @click.prevent="refresh()" 
                        class="btn btn-primary btn-sm" 
                        title="Обновить"
                        style="float:left;margin-right:3px;"
                    >
                        <i class="fa-solid fa-rotate"></i>
                    </button>
                    <h5 style="text-align: left;">Редактор методов оплаты</h5>
                </div>
                
                <div class="card-body" style="text-align:left;">
                    
                    <div class="w-100 text-left">
                        <loader-circle v-if="loading_costs"></loader-circle>
                        <table v-if="!loading_costs" class="text-left table-responsive">
                            <thead class="bg-light">
                                <tr>
                                    <th>ID</th>
                                    <th class="text-primary text-center">Cost</th>
                                    <th class="text-primary text-center">%</th>\
                                    <th class="text-primary text-center">Валюта</th>
                                    <th class="text-primary text-center"></th>
                                    <th class="text-primary text-center"></th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="cost in costs" :class="{'border border-secondary': cost.creating}">
                                    <td style="padding-right: 10px;">
                                        <span v-if="!cost.creating" class="fw-bold" >[[ cost.id ]]</span>
                                        <input v-if="cost.creating" type="text" v-model="cost.id" class="form-control form-control-sm"/>
                                    </td>
                                    <td class="text-primary" style="padding-right: 10px;">
                                        <span v-if="!cost.editing">[[ cost.cost ]]</span>
                                        <input v-if="cost.editing" type="numeric" v-model="cost.cost" style="width: 50px;" class="form-control form-control-sm"/>
                                    </td>
                                    <td :class="{'text-success': cost.is_percents, 'text-secondary': !cost.is_percents}" style="padding-right: 10px;">
                                        <span v-if="!cost.editing">[[ cost.is_percents ]]</span>
                                        <input v-if="cost.editing" type="checkbox" v-model="cost.is_percents" class="form-check-input"/>
                                    </td>
                                    <td style="padding-right: 10px;">
                                        <span v-if="!cost.editing">[[ cost.cur ]]</span>
                                        <input v-if="cost.editing" type="text" v-model="cost.cur" style="width: 50px;" class="form-control form-control-sm"/>
                                    </td>
                                    <td>
                                        <button v-bind:disabled="cost.loading" v-if="!cost.editing" @click.prevent="edit_cost_item(cost, true)" class="btn btn-sm btn-secondary">edit</button>
                                        <button v-bind:disabled="cost.loading" v-if="cost.editing" @click.prevent="cancel_cost_item(cost)" class="btn btn-sm btn-warning">cancel</button>
                                        <button v-bind:disabled="cost.loading" v-if="cost.editing && !cost.creating" @click.prevent="edit_cost_item(cost, false, true)" class="btn btn-sm btn-success">ok</button>
                                        <button v-bind:disabled="cost.loading" v-if="!cost.editing" @click.prevent="delete_cost(cost.id)" class="btn btn-sm btn-danger" title="delete">x</button>

                                        <button v-bind:disabled="cost.loading" v-if="cost.creating" @click.prevent="create_cost(cost)" class="btn btn-sm btn-success">ok</button>
                                    </td>
                                    <td>
                                        <img v-if="cost.loading" src="/static/assets/img/pending-green2.gif" style="max-height: 15px;margin-left:4px;"/>
                                        <span v-if="cost.error" class="text-danger" style="margin-left:4px;">[[ cost.error ]]</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td></td>
                                    <td>
                                        <div class="w-100 text-center">
                                            <button v-if="!cost_create_mode" @click.prevent="make_cost_create_mode(true)" class="btn btn-sm btn-success">+</button>
                                        </div>
                                    </td>
                                    <td></td>
                                </tr>
                            </tbody>
                            
                        </table>
                    </div>
                    <data-table
                        ref="table"
                        style="text-align: left;"
                        :searchable="false"
                        :headers="table.headers"
                        :rows="table.rows"
                        @select_row="on_select_row"
                    ></data-table>
                    <loader-circle v-if="loading_methods"></loader-circle>
                    <div class="w-100 text-center">
                        <button v-if="!loading_methods" @click.prevent="" class="btn btn-sm btn-success">+</button>
                    </div>
                </div>
            </div>
        </div>
        `
    }
);

Vue.component(
    'AdminDirections',
    {
        delimiters: ['[[', ']]'],
        data(){
            return {
                loading: false,
                directions: [],
                icons: {
                    expanded: 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiIHN0YW5kYWxvbmU9Im5vIj8+CgoKCjwhLS0gTGljZW5zZTogUEQuIE1hZGUgYnkgamltbGFtYjogaHR0cHM6Ly9naXRodWIuY29tL2ppbWxhbWIvYm93dGllIC0tPgo8c3ZnIAogICB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iCiAgIHhtbG5zOmNjPSJodHRwOi8vY3JlYXRpdmVjb21tb25zLm9yZy9ucyMiCiAgIHhtbG5zOnJkZj0iaHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4LW5zIyIKICAgeG1sbnM6c3ZnPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIKICAgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIgogICB4bWxuczpzb2RpcG9kaT0iaHR0cDovL3NvZGlwb2RpLnNvdXJjZWZvcmdlLm5ldC9EVEQvc29kaXBvZGktMC5kdGQiCiAgIHhtbG5zOmlua3NjYXBlPSJodHRwOi8vd3d3Lmlua3NjYXBlLm9yZy9uYW1lc3BhY2VzL2lua3NjYXBlIgogICB3aWR0aD0iMzIwIgogICBoZWlnaHQ9IjQ0OCIKICAgdmlld0JveD0iMCAwIDMyMCA0NDgiCiAgIGlkPSJzdmcyIgogICB2ZXJzaW9uPSIxLjEiCiAgIGlua3NjYXBlOnZlcnNpb249IjAuOTEgcjEzNzI1IgogICBzb2RpcG9kaTpkb2NuYW1lPSJ0cmlhbmdsZS1yaWdodC1kb3duLnN2ZyI+CiAgPHRpdGxlCiAgICAgaWQ9InRpdGxlMzMzOCI+dHJpYW5nbGUtcmlnaHQtZG93bjwvdGl0bGU+CiAgPGRlZnMKICAgICBpZD0iZGVmczQiIC8+CiAgPHNvZGlwb2RpOm5hbWVkdmlldwogICAgIGlkPSJiYXNlIgogICAgIHBhZ2Vjb2xvcj0iI2ZmZmZmZiIKICAgICBib3JkZXJjb2xvcj0iIzY2NjY2NiIKICAgICBib3JkZXJvcGFjaXR5PSIxLjAiCiAgICAgaW5rc2NhcGU6cGFnZW9wYWNpdHk9IjAuMCIKICAgICBpbmtzY2FwZTpwYWdlc2hhZG93PSIyIgogICAgIGlua3NjYXBlOnpvb209IjEuOTc5ODk5IgogICAgIGlua3NjYXBlOmN4PSI3My4xNDAxMDgiCiAgICAgaW5rc2NhcGU6Y3k9IjIyMS45NzgxNyIKICAgICBpbmtzY2FwZTpkb2N1bWVudC11bml0cz0icHgiCiAgICAgaW5rc2NhcGU6Y3VycmVudC1sYXllcj0ibGF5ZXIxIgogICAgIHNob3dncmlkPSJ0cnVlIgogICAgIGZpdC1tYXJnaW4tdG9wPSI0NDgiCiAgICAgZml0LW1hcmdpbi1yaWdodD0iMzg0IgogICAgIGZpdC1tYXJnaW4tbGVmdD0iMCIKICAgICBmaXQtbWFyZ2luLWJvdHRvbT0iMCIKICAgICB1bml0cz0icHgiCiAgICAgaW5rc2NhcGU6d2luZG93LXdpZHRoPSIxNjgxIgogICAgIGlua3NjYXBlOndpbmRvdy1oZWlnaHQ9IjEzMzkiCiAgICAgaW5rc2NhcGU6d2luZG93LXg9IjEzMiIKICAgICBpbmtzY2FwZTp3aW5kb3cteT0iNDIzIgogICAgIGlua3NjYXBlOndpbmRvdy1tYXhpbWl6ZWQ9IjAiCiAgICAgaW5rc2NhcGU6c25hcC1iYm94PSJ0cnVlIgogICAgIGlua3NjYXBlOnNuYXAtYmJveC1lZGdlLW1pZHBvaW50cz0iZmFsc2UiCiAgICAgaW5rc2NhcGU6YmJveC1ub2Rlcz0idHJ1ZSI+CiAgICA8aW5rc2NhcGU6Z3JpZAogICAgICAgdHlwZT0ieHlncmlkIgogICAgICAgaWQ9ImdyaWQzMzQ3IgogICAgICAgc3BhY2luZ3g9IjE2IgogICAgICAgc3BhY2luZ3k9IjE2IgogICAgICAgZW1wc3BhY2luZz0iMiIKICAgICAgIG9yaWdpbng9IjAiCiAgICAgICBvcmlnaW55PSItMS43NDk4NDYyZS0wMDUiIC8+CiAgPC9zb2RpcG9kaTpuYW1lZHZpZXc+CiAgPG1ldGFkYXRhCiAgICAgaWQ9Im1ldGFkYXRhNyI+CiAgICA8cmRmOlJERj4KICAgICAgPGNjOldvcmsKICAgICAgICAgcmRmOmFib3V0PSIiPgogICAgICAgIDxkYzpmb3JtYXQ+aW1hZ2Uvc3ZnK3htbDwvZGM6Zm9ybWF0PgogICAgICAgIDxkYzp0eXBlCiAgICAgICAgICAgcmRmOnJlc291cmNlPSJodHRwOi8vcHVybC5vcmcvZGMvZGNtaXR5cGUvU3RpbGxJbWFnZSIgLz4KICAgICAgICA8ZGM6dGl0bGU+dHJpYW5nbGUtcmlnaHQtZG93bjwvZGM6dGl0bGU+CiAgICAgIDwvY2M6V29yaz4KICAgIDwvcmRmOlJERj4KICA8L21ldGFkYXRhPgogIDxnCiAgICAgaW5rc2NhcGU6bGFiZWw9IkxheWVyIDEiCiAgICAgaW5rc2NhcGU6Z3JvdXBtb2RlPSJsYXllciIKICAgICBpZD0ibGF5ZXIxIgogICAgIHRyYW5zZm9ybT0idHJhbnNsYXRlKDAsLTYwNC4zNjIyNCkiPgogICAgPHBhdGgKICAgICAgIHN0eWxlPSJmaWxsLXJ1bGU6ZXZlbm9kZDtzdHJva2U6bm9uZTtzdHJva2Utd2lkdGg6MXB4O3N0cm9rZS1saW5lY2FwOmJ1dHQ7c3Ryb2tlLWxpbmVqb2luOm1pdGVyO3N0cm9rZS1vcGFjaXR5OjEiCiAgICAgICBkPSJtIDI4Ny42NDY3NSw3NzYuNzE1NTEgMCwyMDMuNjQ2NzUgLTIwMy42NDY3NSwwIHoiCiAgICAgICBpZD0icGF0aDMzMzciCiAgICAgICBpbmtzY2FwZTpjb25uZWN0b3ItY3VydmF0dXJlPSIwIiAvPgogIDwvZz4KPC9zdmc+',
                    collapsed: 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiIHN0YW5kYWxvbmU9Im5vIj8+CgoKCjwhLS0gTGljZW5zZTogUEQuIE1hZGUgYnkgamltbGFtYjogaHR0cHM6Ly9naXRodWIuY29tL2ppbWxhbWIvYm93dGllIC0tPgo8c3ZnIAogICB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iCiAgIHhtbG5zOmNjPSJodHRwOi8vY3JlYXRpdmVjb21tb25zLm9yZy9ucyMiCiAgIHhtbG5zOnJkZj0iaHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4LW5zIyIKICAgeG1sbnM6c3ZnPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIKICAgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIgogICB4bWxuczpzb2RpcG9kaT0iaHR0cDovL3NvZGlwb2RpLnNvdXJjZWZvcmdlLm5ldC9EVEQvc29kaXBvZGktMC5kdGQiCiAgIHhtbG5zOmlua3NjYXBlPSJodHRwOi8vd3d3Lmlua3NjYXBlLm9yZy9uYW1lc3BhY2VzL2lua3NjYXBlIgogICB3aWR0aD0iMzIwIgogICBoZWlnaHQ9IjQ0OCIKICAgdmlld0JveD0iMCAwIDMyMCA0NDgiCiAgIGlkPSJzdmcyIgogICB2ZXJzaW9uPSIxLjEiCiAgIGlua3NjYXBlOnZlcnNpb249IjAuOTEgcjEzNzI1IgogICBzb2RpcG9kaTpkb2NuYW1lPSJ0cmlhbmdsZS1yaWdodC1vdXRsaW5lLnN2ZyI+CiAgPHRpdGxlCiAgICAgaWQ9InRpdGxlMzMzOCI+dHJpYW5nbGUtcmlnaHQtb3V0bGluZTwvdGl0bGU+CiAgPGRlZnMKICAgICBpZD0iZGVmczQiIC8+CiAgPHNvZGlwb2RpOm5hbWVkdmlldwogICAgIGlkPSJiYXNlIgogICAgIHBhZ2Vjb2xvcj0iI2ZmZmZmZiIKICAgICBib3JkZXJjb2xvcj0iIzY2NjY2NiIKICAgICBib3JkZXJvcGFjaXR5PSIxLjAiCiAgICAgaW5rc2NhcGU6cGFnZW9wYWNpdHk9IjAuMCIKICAgICBpbmtzY2FwZTpwYWdlc2hhZG93PSIyIgogICAgIGlua3NjYXBlOnpvb209IjEuOTc5ODk5IgogICAgIGlua3NjYXBlOmN4PSI3My4xNDAxMDgiCiAgICAgaW5rc2NhcGU6Y3k9IjIyMS45NzgxNyIKICAgICBpbmtzY2FwZTpkb2N1bWVudC11bml0cz0icHgiCiAgICAgaW5rc2NhcGU6Y3VycmVudC1sYXllcj0ibGF5ZXIxIgogICAgIHNob3dncmlkPSJ0cnVlIgogICAgIGZpdC1tYXJnaW4tdG9wPSI0NDgiCiAgICAgZml0LW1hcmdpbi1yaWdodD0iMzg0IgogICAgIGZpdC1tYXJnaW4tbGVmdD0iMCIKICAgICBmaXQtbWFyZ2luLWJvdHRvbT0iMCIKICAgICB1bml0cz0icHgiCiAgICAgaW5rc2NhcGU6d2luZG93LXdpZHRoPSIxNjgxIgogICAgIGlua3NjYXBlOndpbmRvdy1oZWlnaHQ9IjEzMzkiCiAgICAgaW5rc2NhcGU6d2luZG93LXg9IjEzMiIKICAgICBpbmtzY2FwZTp3aW5kb3cteT0iNDIzIgogICAgIGlua3NjYXBlOndpbmRvdy1tYXhpbWl6ZWQ9IjAiCiAgICAgaW5rc2NhcGU6c25hcC1iYm94PSJ0cnVlIgogICAgIGlua3NjYXBlOnNuYXAtYmJveC1lZGdlLW1pZHBvaW50cz0iZmFsc2UiCiAgICAgaW5rc2NhcGU6YmJveC1ub2Rlcz0idHJ1ZSI+CiAgICA8aW5rc2NhcGU6Z3JpZAogICAgICAgdHlwZT0ieHlncmlkIgogICAgICAgaWQ9ImdyaWQzMzQ3IgogICAgICAgc3BhY2luZ3g9IjE2IgogICAgICAgc3BhY2luZ3k9IjE2IgogICAgICAgZW1wc3BhY2luZz0iMiIKICAgICAgIG9yaWdpbng9IjAiCiAgICAgICBvcmlnaW55PSItMS43NDk4NDYyZS0wMDUiIC8+CiAgPC9zb2RpcG9kaTpuYW1lZHZpZXc+CiAgPG1ldGFkYXRhCiAgICAgaWQ9Im1ldGFkYXRhNyI+CiAgICA8cmRmOlJERj4KICAgICAgPGNjOldvcmsKICAgICAgICAgcmRmOmFib3V0PSIiPgogICAgICAgIDxkYzpmb3JtYXQ+aW1hZ2Uvc3ZnK3htbDwvZGM6Zm9ybWF0PgogICAgICAgIDxkYzp0eXBlCiAgICAgICAgICAgcmRmOnJlc291cmNlPSJodHRwOi8vcHVybC5vcmcvZGMvZGNtaXR5cGUvU3RpbGxJbWFnZSIgLz4KICAgICAgICA8ZGM6dGl0bGU+dHJpYW5nbGUtcmlnaHQtb3V0bGluZTwvZGM6dGl0bGU+CiAgICAgIDwvY2M6V29yaz4KICAgIDwvcmRmOlJERj4KICA8L21ldGFkYXRhPgogIDxnCiAgICAgaW5rc2NhcGU6bGFiZWw9IkxheWVyIDEiCiAgICAgaW5rc2NhcGU6Z3JvdXBtb2RlPSJsYXllciIKICAgICBpZD0ibGF5ZXIxIgogICAgIHRyYW5zZm9ybT0idHJhbnNsYXRlKDAsLTYwNC4zNjIyNCkiPgogICAgPHBhdGgKICAgICAgIHN0eWxlPSJmaWxsLXJ1bGU6ZXZlbm9kZDtzdHJva2U6bm9uZTtzdHJva2Utd2lkdGg6MXB4O3N0cm9rZS1saW5lY2FwOmJ1dHQ7c3Ryb2tlLWxpbmVqb2luOm1pdGVyO3N0cm9rZS1vcGFjaXR5OjEiCiAgICAgICBkPSJNIDk2IDg4IEwgOTYgMzc2IEwgMjQwIDIzMiBMIDk2IDg4IHogTSAxMjggMTY4IEwgMTk2IDIzMiBMIDEyOCAyOTYgTCAxMjggMTY4IHogIgogICAgICAgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMCw2MDQuMzYyMjQpIgogICAgICAgaWQ9InBhdGgzMzM3IiAvPgogIDwvZz4KPC9zdmc+',
                },
            }
        },
        mounted(){
            this.refresh();
        },
        methods: {
            refresh(){
                const self = this;
                self.loading = true;
                axios
                   .get('/api/exchange/directions')
                   .then(
                       (response) => {
                           self.build_directions(response.data);
                           //console.log(self.directions)
                       }
                   ).finally(
                       response => (
                           self.loading = false
                       )
                   )
            },
            build_directions(items){
                for (let i=0; i<items.length; i++) {
                    const item = items[i];
                    for (let k=0; k<item.externals.length; k++) {
                        const s = secs_delta_to_string(item.externals[k].secs_ago);
                        item.externals[k].secs_ago_str = s;
                    }
                    let found = null;
                    for (let j=0; j<this.directions.length; j++) {
                        const dir = this.directions[j];
                        if (dir.id === item.id) {
                            dir.data = item;
                            found = dir;
                            break;
                        }
                    }
                    if (!found) {
                        this.directions.push(
                            {
                                data: item,
                                collapsed: true
                            }
                        );
                    }
                }
            }
        },
        template: `
            <div class="w-100 text-left">
               <div class="card m-1" v-for="dir in directions">
                  <!-- Header -->
                  <div class="card-header">
                     <div class="w-100 row">
                         <button @click="dir.collapsed = !dir.collapsed" class="btn btn-link col-auto" type="button">
                              <img style="max-height: 20px;max-width:20px;margin-right: 5px;" 
                                v-bind:src="dir.collapsed ? icons.collapsed : icons.expanded" 
                              />
                         </button>
                         <directions-header
                            class="col" 
                            :src="dir.data.src"
                            :dest="dir.data.dest"
                            :show_names="false"
                         >   
                         </directions-header>
                     </div>
                  </div>
                  <!-- Body -->
                  <div class="card-body" v-bind:class="{'collapse': dir.collapsed }">
                      <div class="row">
                          <div class="col-6">
                            <div class="w-100 row">
                                <div class="col">
                                    <h6 class="text-success">Клиент отдает <span class="text-primary">[[ dir.data.src.code ]]</span></h6>
                                    <!---- SRC --->
                                    <span class="text-secondary">Валюта</span>
                                    <span class="text-primary">[[ dir.data.src.cur.symbol ]]</span>
                                    <img v-bind:src="dir.data.src.cur.icon" v-if="dir.data.src.cur.icon" style="max-height:1.1em;"/>
                                    <div class="w-100"></div>
                                    <span class="text-secondary">Метод</span>
                                    <span class="text-primary">[[ dir.data.src.method.name ]]</span>
                                    <img v-bind:src="dir.data.src.method.icon" v-if="dir.data.src.method.icon" style="max-height:1.1em;"/>
                                    <div class="w-100"></div>
                                    <span class="bg-primary badge">[[ dir.data.src.method.category ]]</span>
                                    <span class="bg-primary badge">[[ dir.data.src.method.sub ]]</span>
                                    <div class="w-100"></div>
                                    <span class="text-secondary">Owner</span>
                                    <span class="text-primary">[[ dir.data.src.method.owner_did ]]</span>
                                    <div class="w-100"></div>
                                    <span class="text-secondary">Enabled</span>
                                    <span class="text-primary">[[ dir.data.src.method.is_enabled ]]</span>
                                </div>
                                <span class="col text-center">&rarr;</span>
                                <div class="col">
                                    <h6 class="text-success">Клиент получает</h6>
                                    <!---- DEST --->
                                    <span class="text-secondary">Валюта</span>
                                    <span class="text-primary">[[ dir.data.dest.cur.symbol ]]</span>
                                    <img v-bind:src="dir.data.dest.cur.icon" v-if="dir.data.dest.cur.icon" style="max-height:1.1em;"/>
                                    <div class="w-100"></div>
                                    <span class="text-secondary">Метод</span>
                                    <span class="text-primary">[[ dir.data.dest.method.name ]]</span>
                                    <img v-bind:src="dir.data.dest.method.icon" v-if="dir.data.dest.method.icon" style="max-height:1.1em;"/>
                                    <div class="w-100"></div>
                                    <span class="bg-primary badge">[[ dir.data.dest.method.category ]]</span>
                                    <span class="bg-primary badge">[[ dir.data.dest.method.sub ]]</span>
                                    <div class="w-100"></div>
                                    <span class="text-secondary">Owner</span>
                                    <span class="text-primary">[[ dir.data.dest.method.owner_did ]]</span>
                                    <div class="w-100"></div>
                                    <span class="text-secondary">Enabled</span>
                                    <span class="text-primary">[[ dir.data.dest.method.is_enabled ]]</span>
                                </div>
                            </div>
                          </div>
                          <div class="col-3">
                            <ul v-for="ext in dir.data.externals" style="font-size: 80%;">
                                <li>
                                   <span class="text-primary">[[ ext.rate.toLocaleString() ]]</span>
                                   <span style="margin-right:1%;" class="bg bg-secondary rounded p-1 text-light">
                                        [[ ext.scope ]]
                                   </span>
                                   <span class="text-secondary">
                                     [[ ext.src ]] &rarr; [[ ext.dest ]]
                                     ([[ ext.engine ]]) 
                                   </span>
                                   <br/>
                                   <span>
                                      [[ ext.secs_ago_str ]] назад
                                   </span>
                                </li>
                            </ul>
                          </div>
                      </div>
                  </div>
               </div>
            </div>
        `
    }
);


Vue.component(
    'Any',
    {
        props: {
            header: {
                type: String,
                default: "--- Any ---"
            },
        },
        delimiters: ['[[', ']]'],
        template: `
            <div class="w-100 text-center">
                <div class="alert alert-danger">
                    <h4>Модуль не подключен</h4>
                    <p>Обратитесь к администратору сервиса за консультацией</p>
                </div>
            </div>
        `
    }
);


Vue.component(
    'mass-payments',
    {
        props: {
            header: {
                type: String,
                default: "Mass Payments"
            },
            base_url: String,
            can_process: {
                type: Boolean,
                default: false
            },
            can_edit_settings: {
                type: Boolean,
                default: true
            },
            can_deposit: {
                type: Boolean,
                default: true
            }
        },
        delimiters: ['[[', ']]'],
        data() {
            return {
                table: [],
                loaded: false,
                checked_collection: {},
                refreshing_table: false,
                error_msg: null,
                checked_all: false,
                check_counter: 0,
                icons: {
                    settings: 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCEtLSBMaWNlbnNlOiBDQyBBdHRyaWJ1dGlvbi4gTWFkZSBieSBzYWxlc2ZvcmNlOiBodHRwczovL2xpZ2h0bmluZ2Rlc2lnbnN5c3RlbS5jb20vIC0tPgo8c3ZnIGZpbGw9IiMwMDAwMDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgCgkgd2lkdGg9IjgwMHB4IiBoZWlnaHQ9IjgwMHB4IiB2aWV3Qm94PSIwIDAgNTIgNTIiIGVuYWJsZS1iYWNrZ3JvdW5kPSJuZXcgMCAwIDUyIDUyIiB4bWw6c3BhY2U9InByZXNlcnZlIj4KPGc+Cgk8cGF0aCBkPSJNMjYuMSwxOS4xYy0zLjksMC03LDMuMS03LDdzMy4xLDcsNyw3czctMy4xLDctN1MzMCwxOS4xLDI2LjEsMTkuMXoiLz4KCTxwYXRoIGQ9Ik00Ny4xLDMyLjRsLTMuNy0zLjFjMC4yLTEuMSwwLjMtMi4zLDAuMy0zLjRjMC0xLjEtMC4xLTIuMy0wLjMtMy40bDMuNy0zLjFjMS4yLTEsMS42LTIuOCwwLjgtNC4yCgkJbC0xLjYtMi44Yy0wLjYtMS0xLjctMS42LTIuOS0xLjZjLTAuNCwwLTAuOCwwLjEtMS4xLDAuMmwtNC42LDEuN2MtMS44LTEuNi0zLjgtMi43LTUuOS0zLjRMMzEsNC42Yy0wLjMtMS42LTEuNy0yLjUtMy4zLTIuNWgtMy4yCgkJYy0xLjYsMC0zLDAuOS0zLjMsMi41bC0wLjgsNC42Yy0yLjIsMC43LTQuMiwxLjktNiwzLjRsLTQuNi0xLjdjLTAuNC0wLjEtMC43LTAuMi0xLjEtMC4yYy0xLjIsMC0yLjMsMC42LTIuOSwxLjZsLTEuNiwyLjgKCQljLTAuOCwxLjQtMC41LDMuMiwwLjgsNC4ybDMuNywzLjFjLTAuMiwxLjEtMC4zLDIuMy0wLjMsMy40YzAsMS4yLDAuMSwyLjMsMC4zLDMuNEw1LDMyLjNjLTEuMiwxLTEuNiwyLjgtMC44LDQuMmwxLjYsMi44CgkJYzAuNiwxLDEuNywxLjYsMi45LDEuNmMwLjQsMCwwLjgtMC4xLDEuMS0wLjJsNC42LTEuN2MxLjgsMS42LDMuOCwyLjcsNS45LDMuNGwwLjgsNC44YzAuMywxLjYsMS42LDIuNywzLjMsMi43aDMuMgoJCWMxLjYsMCwzLTEuMiwzLjMtMi44bDAuOC00LjhjMi4zLTAuOCw0LjQtMiw2LjItMy43bDQuMywxLjdjMC40LDAuMSwwLjgsMC4yLDEuMiwwLjJjMS4yLDAsMi4zLTAuNiwyLjktMS42bDEuNS0yLjYKCQlDNDguNywzNS4yLDQ4LjMsMzMuNCw0Ny4xLDMyLjR6IE0yNi4xLDM3LjFjLTYuMSwwLTExLTQuOS0xMS0xMXM0LjktMTEsMTEtMTFzMTEsNC45LDExLDExUzMyLjIsMzcuMSwyNi4xLDM3LjF6Ii8+CjwvZz4KPC9zdmc+'
                },
                labels: {
                    deposit: 'Депозит',
                    deposit_balance: 'Пополнить баланс',
                    settings: 'Настройки',
                    payment_method: 'Платежный метод',
                    address: 'Адрес',
                    rates: 'Курс взаимозачетов',
                    balance: 'Баланс',
                    total: 'Всего',
                    reserve: 'Резерв',
                    orders: 'Заявки',
                    record_empty: 'Запись не выбрана',
                    filters: 'Фильтры',
                    refresh: 'Обновить',
                    selected: 'Выбрано',
                    make_records_processing: 'Взять записи в работу',
                    no_records_checked: 'Не выбрано записей',
                    amount: 'Сумма',
                    deposit_wait_approve: 'Депозиты ожидаются'
                },
                assets: {
                    loading: true,
                    error: null,
                    data: null,
                    editing_data: null,
                    edited: false,
                    editable: this.can_edit_settings
                },
                deposit: {
                    base: null,
                    quote: 1000.0,
                    min: 1000.0,
                    pending: [],
                    loading: false,
                    error_msg: null
                },
                table_api: null,
                selected_row: null,
                details: {
                    tab: 0
                },
                show_deposit_window: false,
                filters: [
                    {
                        label: 'pending',
                        value: 'pending',
                        checked: false,
                        class: 'btn-primary',
                        single: false,
                    },
                    {
                        label: 'error',
                        value: 'error',
                        checked: false,
                        class: 'btn-danger',
                        single: false
                    },
                    {
                        label: 'success',
                        value: 'success',
                        checked: false,
                        class: 'btn-success',
                        single: false,
                    },
                    {
                        label: 'All',
                        value: 'all',
                        checked: true,
                        class: 'btn-dark',
                        single: true
                    }
                ]
            }
        },
        mounted () {
            this.refresh('table');
            this.refresh('assets');
            this.refresh('deposit');

            let self = this;
            const renderRow = function(rowValue, tr, index){
                if (self.selected_row && self.selected_row.index === index) {
                    tr.attributes.class = "table-primary";
                }
            }

            const renderStatus = function(data, cell, dataIndex, cellIndex) {
                cell.attributes = {
                    class: 'text-primary'
                };
                const value = data[0].data;
                if (['pending', 'processing'].includes(value)) {
                    if (value === 'processing') {
                        cell.childNodes[0].data = 'process';
                    }
                    cell.childNodes.push({
                        nodeName: "IMG",
                        attributes: {
                            "src": '/static/assets/img/pending-green2.gif',
                            "style": "max-height: 15px;margin-left:4px;"
                        }
                    })
                }
                if (['error'].includes(value)) {
                    cell.attributes.class = 'text-danger';
                }
                if (['success'].includes(value)) {
                    cell.attributes.class = 'text-success';
                }
                if (['processing'].includes(value)) {
                    cell.attributes.class = 'text-success';
                }
                cell.attributes.class += ' font-weight-bold';
            }

            const renderCheckBox = function(data, cell, dataIndex, cellIndex) {
                cell.attributes = {
                    class:"text-center"
                }
                return `<span class="checkbox">${data[0].data === 'true' ? "☑" : "☐"}</span>`;
            }

            const renderBankAccount = function(data, cell, dataIndex, dellIndex) {
                try {
                    const value = cell.childNodes[0].data;
                    cell.childNodes[0].data = cc_format(value);
                }catch (e) {
                    console.log(e)
                }
            }

            this.table_api = new simpleDatatables.DataTable(
                this.$refs.table,
                {
                    perPageSelect: [20, 50, 150],
                    rowRender: renderRow,
                    columns: [
                        {
                            select: 0,
                            hidden: true,
                            sortable: false,
                            type: "string"
                        },
                        {
                            select: 1,
                            type: "bool",
                            sortable: false,
                            render: renderCheckBox,
                            hidden: this.can_process !== true
                        },
                        {
                            select: 2,
                            type: "string"
                        }, {
                            select: 3,
                            type: "string"
                        }, {
                            select: 4,
                            render: renderStatus,
                            type: "string"
                        }, {
                            select: 5,
                            type: "string"
                        }, {
                            select: 6,
                            sortable: false,
                            type: "string",
                            render: renderBankAccount
                        },{
                            select: 7,
                            type: "string"
                        }
                    ]
                }
            );
            this.table_api.on("datatable.selectrow", (rowIndex, event) => {
                event.preventDefault();
                if (isNaN(rowIndex)) {
                    return;
                }
                let uid = this.table_api.data.data[rowIndex][0].text;
                if (event.target.matches("span.checkbox")) {
                    return;
                }
                let row = this.find_table_row(uid);
                if (row) {
                    this.selected_row = row;
                    // Rendering
                    this.table_api.update();
                }
            });
            self = this;
            this.table_api.dom.addEventListener("click", event => {
                if (event.target.matches("span.checkbox")) {
                    event.preventDefault()
                    event.stopPropagation()
                    const name = event.target.parentElement.parentElement.dataset.name
                    const index = parseInt(event.target.parentElement.parentElement.dataset.index, 10)
                    //console.log(index);
                    const row = self.table_api.data.data[index]
                    const cell = row[1]
                    const checked = cell.data[0].data === 'true';
                    const uid = row[0].text;
                    self = this
                    //console.log('Checked: ' + uid);
                    if (checked) {
                        cell.data[0].data = 'false';
                        delete self.checked_collection[uid];
                        self.checked_all = false;
                    }
                    else {
                        cell.data[0].data = 'true';
                        self.checked_collection[uid] = true;
                    }
                    self.check_counter ++;
                    self.table_api.update()
                }
            });
            document.tbl = this.table_api
        },
        computed: {
            api_base(){
                return this.base_url;
            },
            filtered_table(){
                if (!this.table) {
                    return [];
                }
                let tbl = [];
                for (let i=0; i<this.table.length; i++){
                    let o = this.table[i];
                    let row = {
                        no: i+1,
                        data: o
                    }
                    tbl.push(row)
                }
                return tbl;
            },
            checked_rows_count(){
                if (this.check_counter > 0) {
                    // если убрать то значение перестанет пересчитываться
                }
                return Object.keys(this.checked_collection).length;
            }
        },
        methods: {
            refresh(resource, ignore_loading=false){
                let self = this;
                if (resource === 'table') {
                    self.selected_row = null;
                    let params = new URLSearchParams();
                    this.filters_2_statuses().forEach((value, index) => {
                        params.append(`status`, value);
                    });
                    console.log('Refresh mass-payments table');
                    if (self.loaded) {
                        self.refreshing_table = true;
                    }
                    axios
                        .get(
                            self.api_base,
                            {
                                params: params
                            }
                        )
                        .then(
                            (response) => {
                                self.table = response.data;
                                self.checked_collection = {};
                                self.check_counter ++;
                                self.checked_all = false;
                                self.refresh_table();
                            }
                        ).catch(
                            (e) => {
                               self.error_msg = e.message || e.response.statusText
                            }
                        ).finally(
                            (response) => {
                                self.loaded = true;
                                self.refreshing_table = false;
                            }
                    )
                }
                if (resource === 'assets') {
                    if (!ignore_loading) {
                        self.assets.loading = true;
                    }
                    self.assets.error = null;
                    console.log('Refresh mass-payments assets');
                    axios
                        .get(self.api_base + '/assets')
                        .then(
                            (response) => {
                                self.assets.data = response.data;
                                let obj = {}
                                for (let attr in response.data) {
                                    obj[attr] = response.data[attr];
                                }
                                self.assets.editing_data = obj;
                                self.changed_deposit_value()
                            }
                        ).catch(
                            (e) => {
                               self.assets.error = e.response.data || e.response.statusText
                            }
                        ).finally(
                        () => {
                            self.assets.loading = false;
                        })

                }
                if (resource === 'deposit') {
                    self.deposit.loading = true;
                    self.deposit.error_msg = null;
                    console.log('Refresh deposit');
                    axios
                        .get(self.api_base + '/deposit?status=pending')
                        .then(
                            (response) => {
                                self.deposit.pending = response.data;
                            }
                        ).catch(
                            (e) => {
                               self.deposit.error_msg = e.response.data || e.response.statusText
                            }
                        ).finally(
                        () => {
                            self.deposit.loading = false;
                        })
                }
            },
            refresh_table(){
                if (!this.table) {
                    return;
                }
                let updData = [];

                function add_col(value, container){
                    container.push({
                        data: [
                            {
                                "nodeName": "#text",
                                "data": value.toString()
                            }
                        ],
                        text: value.toString(),
                        order: value
                    });
                }

                for (let i=0; i<this.table.length; i++) {
                    let src = this.table[i];
                    src.index = i;
                    let dest = [];
                    add_col(src.uid, dest);
                    add_col(false, dest);
                    add_col(src.transaction.order_id, dest);
                    add_col(src.transaction.amount, dest);
                    add_col(src.status.status, dest);
                    add_col(src.customer.identifier, dest);
                    add_col(src.card.number, dest);
                    add_col(format_datetime_str(src.utc), dest);
                    updData.push(dest);
                }
                this.table_api.data.data = updData;
                this.table_api.refresh();
            },
            find_table_row(uid) {
                if (!this.table) {
                    return null;
                }
                for(let i=0; i<this.table.length; i++) {
                    let row = this.table[i];
                    if (row.uid === uid) {
                        return row;
                    }
                }
                return null;
            },
            filters_2_statuses(){
                let statuses = [];
                for (let i in this.filters) {
                    let item = this.filters[i];
                    if (item.checked) {
                        statuses.push(item.value);
                    }
                }
                if (statuses.includes('all')){
                    return []
                }
                else {
                    return statuses;
                }
            },
            filters_changed(){
                this.refresh('table');
            },
            toggle_checkall() {
                const checked = !this.checked_all;
                if (checked) {
                    // check all rows
                    for(let i=0; i<this.table_api.data.data.length; i++) {
                        let row = this.table_api.data.data[i];
                        let uid = row[0].data[0].data;
                        this.checked_collection[uid] = true;
                        row[1].data[0].data = 'true'
                    }
                }
                else {
                    // clear all checked
                    this.checked_collection = {};
                    for(let i=0; i<this.table_api.data.data.length; i++) {
                        let row = this.table_api.data.data[i];
                        row[1].data[0].data = 'false'
                    }
                }
                this.table_api.update();
                this.checked_all = checked;
                this.check_counter ++;
            },
            clear(){
                this.table = [];
                this.loaded = false;
                this.checked_collection={};
                this.check_counter ++;
                this.refreshing_table=false;
                this.error_msg=null;
                this.checked_all=false;
                this.assets.loading = true;
                this.assets.error=null;
                this.assets.data=null;
                this.assets.edited=false;
                //this.assets.editable=false; всегда равно can_edit_settings
                this.selected_row=null;
                if (this.table_api) {
                    this.table_api.data.data = [];
                    this.table_api.update();
                }
            },
            process_checked_records(){

                self = this;
                /*
                function mark_checked_rows() {
                    for (let i = 0; i<self.table_api.data.data.length; i++) {
                        let row = self.table_api.data.data[i];
                        let uid = row[0].data[0].data;
                        if (uid in self.checked_collection) {
                            row[4].data[0].data = 'processing';
                            row[1].data[0].data = 'false'
                        }
                    }
                    self.checked_collection = {};
                    self.check_counter ++;
                    self.checked_all = false;
                    self.table_api.update();
                    // self.refresh('table');
                }*/

                let json = [];
                for (let uid in self.checked_collection) {
                    json.push({uid: uid, status: 'processing'});
                }
                const payload = JSON.stringify(json);
                const config = {
                    headers: {'Content-Type': 'application/json'}
                }
                axios
                    .post(
                        self.api_base + '/status', payload, config
                    )
                    .then(
                        (response) => {
                            //mark_checked_rows();
                            self.refresh('table');
                        }
                    ).catch(
                        (e) => {
                            //
                        }
                    ).finally(
                        () => {
                            //
                        }
                    )
            },
            edit_assets(){
                const self = this;
                const payload = JSON.stringify(this.assets.editing_data);
                const config = {
                    headers: {'Content-Type': 'application/json'}
                }
                self.assets.loading = true;
                axios
                   .post(
                       '/api/mass-payments/assets', payload, config
                   )
                   .then(
                       (response) => {
                           self.assets.error = null;
                           self.assets.data = response.data;
                           let obj = {}
                           for (let attr in response.data) {
                               obj[attr] = response.data[attr];
                           }
                           self.assets.editing_data = obj;
                       }
                   ).catch(
                        (e) => {
                            self.assets.error = 'Error';
                        }
                   ).finally(
                        () => {
                            self.assets.loading = false;
                        }
                   )
            },
            open_deposit_window(){
                if (this.assets.data) {
                    this.deposit.loading = false;
                    this.deposit.error_msg = null;
                    this.show_deposit_window = true
                }
            },
            changed_deposit_value(source='quote'){
                if (this.deposit.quote === null || this.deposit.quote < 0) {
                    this.deposit.quote = 0.0;
                }
                if (this.deposit.base === null || this.deposit.base < 0) {
                    this.deposit.base = 0.0;
                }
                if (source === 'quote') {
                    this.deposit.base = this.deposit.quote * this.assets.data.ratios.ratio
                }
                if (source === 'base') {
                    this.deposit.quote = this.deposit.base / this.assets.data.ratios.ratio
                }
                this.deposit.quote = Math.trunc(this.deposit.quote);
                this.deposit.base = Math.trunc(this.deposit.base);

                if (this.deposit.quote < this.deposit.min) {
                    this.deposit.quote = this.deposit.min;
                    //this.changed_deposit_value('quote')
                }
            },
            new_deposit(){
                const self = this;
                console.log('New deposit');

                axios
                    .post(
                        self.api_base + '/deposit',
                        JSON.stringify({amount: self.deposit.quote}),
                        {
                            headers: {'Content-Type': 'application/json'}
                        }
                    )
                    .then(
                        (response) => {
                            self.refresh('deposit');
                            self.show_deposit_window = false;
                        }
                    ).catch(
                        (e) => {
                           self.deposit.error_msg = e.response.data || e.response.statusText
                        }
                    ).finally(
                    () => {
                        self.deposit.loading = false;
                    })
            }
        },
        watch: {
            base_url(newVal, oldVal){
                this.clear();
                this.refresh('table');
                this.refresh('assets');
            }
        },
        template: `
            <div class="w-100 row">
            
                <modal-window v-if="show_deposit_window" @close="show_deposit_window = false" :width="'30%'" :height="'70%'">
                    <div slot="header" class="w-100">
                        <h3>Deposit
                            <button class="btn btn-danger" @click="show_deposit_window = false" style="float: right;">
                                Close
                            </button>
                        </h3>
                    </div>
                    <div slot="body" class="w-100" style="overflow: auto;">
                        [[ labels.rates ]]:&ensp;
                            <b>[[ assets.data.ratios.ratio ]]&ensp;</b>[[ assets.data.ratios.base ]]/[[ assets.data.ratios.quote ]]
                            &ensp;<b>[[ assets.data.ratios.engine ]]</b>
                        <div class="form-group m-lg-2">
                            <label for="input-deposit-quote">[[ labels.amount ]] <b>[[ assets.data.ratios.quote ]]</b>(min: [[ deposit.min ]])</label>
                            <input v-model="deposit.quote" @input="changed_deposit_value('quote')" id="input-deposit-quote" type="number" class="form-control"/>
                            <label for="input-deposit-base">[[ labels.amount ]] <b>[[ assets.data.ratios.base ]]</b></label>
                            <input v-model="deposit.base" @input="changed_deposit_value('base')" id="input-deposit-base" type="number" class="form-control"/>
                        </div>
                        <div class="w-100 text-center">
                            <p class="text-danger">[[ deposit.error_msg ]]</p>
                            <button v-if="!deposit.loading" class="col btn btn-primary" @click.prevent="new_deposit" type="submit">Submit</button>
                            <img v-if="deposit.loading" class="col" src="/static/assets/img/pending-green2.gif" style="max-height:25px;max-width:25px;"/>
                        </div>
                    </div>
                    <div slot="footer" class="w-100 text-center"></div>
                </modal-window>
                
                <div v-if="error_msg" class="alert alert-danger text-center">
                    <p>[[ error_msg ]]</p>
                </div>
                <!--   Header Cards -->
                <div class="row">
                  <div class="col-sm-6 align-items-stretch">
                    <div class="card">
                      <div class="card-body">
                        <h5 class="card-title">
                            <countdown-timer 
                                style="float:left;"
                                @finished="refresh('assets', true);refresh('deposit', true)"
                            ></countdown-timer>
                            [[ labels.balance ]]&ensp;
                            <span class="text-success" v-if="assets.data">[[ assets.data.balance ]]</span>&ensp;
                            <span class="text-success" v-if="assets.data">[[ assets.data.ratios.quote ]]</span>&ensp;
                            <button @click.prevent="open_deposit_window" style="float:right;" v-if="can_deposit" class="btn btn-sm btn-success" v-bind:title="labels.deposit_balance">+</button>
                        </h5>
                        <div class="w-100 row">
                            <p v-if="assets.data" class="card-text col-8">
                                [[ assets.data.code ]]:&ensp;[[ assets.data.address ]]
                                <br>
                                [[ labels.rates ]]:&ensp;
                                <b>[[ assets.data.ratios.ratio ]]&ensp;</b>[[ assets.data.ratios.base ]]/[[ assets.data.ratios.quote ]]
                                &ensp;<b>[[ assets.data.ratios.engine ]]</b>
                            </p>
                            <div class="col text-success" v-if="can_deposit && deposit.pending.length > 0 && assets.data">
                                <span>[[ labels.deposit_wait_approve ]]</span>
                                <ul class="text-left" style="list-style: none;">
                                    <li v-for="deposit in deposit.pending">
                                        <img style="max-height:20px;" src="/static/assets/img/pending-green.gif" />
                                       <a class="text-danger" href="" @click.prevent="">
                                        [[ deposit.amount ]] [[ assets.data.ratios.quote ]]
                                        </a> 
                                    </li>
                                </ul>
                            </div>
                        </div>
                        <div v-if="assets.data" class="w-100">
                            <span class="text-primary">[[ labels.deposit ]]:&ensp;</span>
                            <span class="text-primary"><b>[[ assets.data.deposit ]]</b></span>
                            <span class="text-muted">/</span>
                            <span class="text-danger">[[ labels.reserve ]]:&ensp;</span>
                            <span class="text-danger"><b>[[ assets.data.reserved ]]</b></span>&ensp;
                            <span class="text-muted">[[ assets.data.ratios.quote ]]</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="col-sm-6 d-flex">
                    <div class="card">
                      <div class="card-body">
                        <h5 class="card-title">[[ labels.settings ]]</h5>
                        <loader-circle v-if="assets.loading"></loader-circle>
                        <div v-if="assets.data" class="row w-100">
                            <p class="card-text col">
                                <b>WebHook:</b>&ensp;
                                <span v-if="!assets.editable" class="text-primary">[[ assets.data.webhook ]]</span>
                            </p>
                            <input
                                placeholder="Enter Webhook URL" 
                                style="min-width: 200px;margin-left: 10px;" 
                                v-if="assets.editable" 
                                class="col form-control" 
                                type="text" 
                                v-model="assets.editing_data.webhook"
                            />
                        </div>
                        <div v-if="assets.editable" class="w-100 text-center m-2">
                            <p class="text-danger">[[ assets.error ]]</p>
                           <button @click.prevent="edit_assets" class="btn btn-primary">Submit</button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- Tables -->
                <div class="w-100 row mt-3 text-center" v-if="!loaded" >
                    <loader style="position:absolute; z-index:1000;"></loader>
                </div>
                <div class="w-100 row mt-3">
                    <div class="col-sm-8">
                        <div class="card">
                            <div class="card-header">
                                <i class="fas fa-table m-1 pl-lg-5"></i>
                                [[ labels.orders ]]
                                <button @click.prevent="refresh('table')" class="btn btn-primary btn-sm" v-bind:title="labels.refresh">
                                    <i class="fa-solid fa-rotate"></i>
                                </button>
                            </div>
                            <div class="card-body">
                                <div class="w-100 mb-1 border border-opacity-50 rounded p-2">
                                    <filters-block 
                                        :items="filters"
                                        @changed="filters_changed"
                                    ></filters-block>
                                    <button @click.prevent="process_checked_records" class="btn btn-sm btn-primary" v-if="checked_rows_count > 0 && can_process">
                                        [[ labels.make_records_processing ]] 
                                        ([[ labels.selected ]]: [[checked_rows_count]])
                                    </button>
                                     <button class="btn btn-sm btn-secondary" v-if="checked_rows_count == 0 && can_process">
                                        [[ labels.no_records_checked ]]
                                     </button>
                                </div>
                                <loader-circle
                                    v-if="refreshing_table"
                                    style="position: absolute;top:50%;"
                                ></loader-circle>
                                <table ref="table" class="w-100 table table-striped table-hover" style="cursor:pointer;">
                                    <thead>
                                        <tr>
                                            <th>UID</th>
                                            <th @click.prevent="toggle_checkall">
                                                Checked
                                                <span
                                                    ref="checkall" 
                                                >
                                                    [[checked_all ? '☑' : '☐']]
                                                </span>
                                            </th>
                                            <th>Txn</th>
                                            <th>Amount</th>
                                            <th>Status</th>
                                            <th>Identity</th>
                                            <th>Card</th>
                                            <th>UTC</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                    <div  class="col-sm-4">
                        <div class="card">
                            <div class="card-header">
                                Details 
                                <b v-if="selected_row">Txn: </b>
                                <span class="text-primary">[[selected_row ? selected_row.transaction.order_id: '']]</span>
                                <b v-if="selected_row">identifier: </b>
                                <span class="text-primary">[[selected_row ? selected_row.customer.identifier: '']]</span>
                            </div>
                            <div class="card-body">
                                <div class="alert alert-danger text-center" v-if="!selected_row">
                                    [[ labels.record_empty ]]
                                </div>
                                <div class="w-100" v-if="selected_row">
                                    <ul class="nav nav-tabs" id="myTab" role="tablist">
                                      <li class="nav-item">
                                        <a 
                                            @click.prevent="details.tab = 0"
                                            v-bind:class="{'active': details.tab === 0}"
                                            class="nav-link" href="#account" 
                                            role="tab" aria-controls="account" aria-selected="true"
                                        >Info</a>
                                      </li>
                                      <li class="nav-item">
                                        <a 
                                            @click.prevent="details.tab = 1"
                                            v-bind:class="{'active': details.tab === 1}"
                                            class="nav-link" href="#merchant" 
                                            role="tab" aria-controls="merchant" aria-selected="false"
                                        >History</a>
                                      </li>
                                    </ul>
                                    <div class="tab-content p-4 border border-light">
                                      <div 
                                            v-bind:class="{'active': details.tab === 0, 'show': details.tab === 0}"
                                            class="tab-pane fade" 
                                            role="tabpanel"
                                      >
                                        <!-- -->
                                        <object-info 
                                            :object="selected_row.status"
                                            :hidden="['payload']"
                                            :header="'Status'"
                                            :attr_class="{
                                                'false': 'text-secondary',
                                                'true': 'text-success',
                                                'error': 'badge bg-danger',
                                                'message': 'badge bg-info',
                                                'pending': 'badge bg-primary',
                                                'success': 'badge bg-success',
                                                'processing': 'badge bg-primary',
                                                'type': 'badge bg-secondary'
                                            }"
                                        >
                                        </object-info>
                                        <!-- -->
                                        <object-info
                                            :object="selected_row.proof"
                                            :header="'Proof'"
                                        >
                                        </object-info>
                                        <!-- -->
                                        <object-info 
                                            :object="selected_row.transaction"
                                            :header="'Transaction'"
                                        >
                                        </object-info>
                                        <!-- -->
                                        <object-info 
                                            :object="selected_row.customer"
                                            :header="'Customer'"
                                        >
                                        </object-info>
                                        <!-- -->
                                        <object-info 
                                            :object="selected_row.card"
                                            :header="'Card'"
                                        >
                                        </object-info>
                                      </div>
                                      <div 
                                            v-bind:class="{'active': details.tab === 1, 'show': details.tab === 1}" 
                                            class="tab-pane fade" 
                                            role="tabpanel"
                                      >
                                        <mass-payment-order-history
                                            :api_base="api_base"
                                            :uid="selected_row.uid"
                                        >
                                        </mass-payment-order-history>
                                      </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                
                </div>
            </div>
        `
    }
);

Vue.component(
    'MerchantMassPayments',
    {
        props: {
            header: {
                type: String,
                default: "Mass Payments"
            },
        },
        delimiters: ['[[', ']]'],
        computed: {
            base_url(){
                return '/api/mass-payments';
            }
        },
        template: `
            <div class="w-100 row">
                <mass-payments
                    :header="header"
                    :base_url="base_url"
                    :can_process="false"
                >
                </mass-payments>
            </div>
        `
    }
);
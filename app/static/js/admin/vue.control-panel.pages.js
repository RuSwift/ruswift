Vue.component(
    'ControlPanelMassPayments',
    {
        props: {
            header: {
                type: String,
                default: "Mass Payments"
            },
            merchant: {
                type: String,
                default: null
            },
        },
        delimiters: ['[[', ']]'],
        computed: {
            base_url(){
                return '/api/control-panel/' + this.merchant + '/mass-payments';
            }
        },
        template: `
            <div class="w-100 row">
                <mass-payments
                    :header="header"
                    :base_url="base_url"
                    :can_process="true"
                    :can_edit_settings="false"
                    :can_deposit="false"
                >
                </mass-payments>
            </div>
        `
    }
);

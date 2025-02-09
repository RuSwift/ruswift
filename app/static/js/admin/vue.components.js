
function generateUUID() { // Public Domain/MIT
    var d = new Date().getTime();//Timestamp
    var d2 = ((typeof performance !== 'undefined') && performance.now && (performance.now()*1000)) || 0;//Time in microseconds since page-load or 0 if unsupported
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16;//random number between 0 and 16
        if(d > 0){//Use timestamp until depleted
            r = (d + r)%16 | 0;
            d = Math.floor(d/16);
        } else {//Use microseconds since page-load if supported
            r = (d2 + r)%16 | 0;
            d2 = Math.floor(d2/16);
        }
        return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
}

function format_datetime_str(s) {
    if (s) {
        const parts1 = s.split('.');
        const dt = parts1[0].split('T');
        let date = dt[0];
        date = date.split('-').reverse().join('.');
        let time = dt[1];
        return time + ' ' + date;
    }
    else {
        return null
    }
}

function cc_format(value) {
    let v = value.replace(/\s+/g, '').replace(/[^0-9]/gi, '')
    let matches = v.match(/\d{4,16}/g);
    let match = matches && matches[0] || ''
    let parts = []

    for (let i=0, len=match.length; i<len; i+=4) {
        parts.push(match.substring(i, i+4))
    }

    if (parts.length) {
        return parts.join(' ')
    } else {
        return value
    }
}

Vue.component('rates-external', {
    delimiters: ['[[', ']]'],
    props: {
        url: {
            default() {
                return "/api/ratios/external";
            }
        },
        title: {
            default(){
                return "Market rates"
            }
        }
    },
    data() {
        return {
            table: [],
            loaded: false
        }
    },
    mounted () {
        this.refresh();
    },
    computed: {
        filtered_table(){
            let tbl = [];
            for (let i=0; i<this.table.length; i++) {
                const row = this.table[i];
                tbl.push(
                    {
                        scope: row.scope,
                        engine: this.format_engine(row.scope, row.engine),
                        give: {
                            symbol: row.give.symbol,
                            value: this.format_float_value(row.give.value),
                            method: row.give.method === "market" ? "Spot" : row.give.method
                        },
                        get: {
                            symbol: row.get.symbol,
                            value: this.format_float_value(row.get.value),
                            method: row.get.method === "market" ? "Spot" : row.get.method
                        }
                    }
                );
            }

            function compare( a, b ) {
              if ( a.scope < b.scope ){
                return -1;
              }
              if ( a.scope > b.scope ){
                return 1;
              }
              if (a.give.symbol < b.get.symbol) {
                  return -1;
              }
              if (a.give.symbol > b.get.symbol) {
                  return 1;
              }
              return 0;
            }

            tbl.sort( compare )
            return tbl;
        }
    },
    methods: {
        refresh(){
            let self = this;
            self.loaded = false;
            axios
               .get('/api/ratios/external')
               .then(
                   response => (
                       self.table = response.data
                       //this.info = response
                   )
               ).finally(
                   response => (
                       self.loaded = true
                   )
               )
        },
        format_float_value(val) {
            return parseFloat(val).toFixed(2)
        },
        format_engine(scope, val) {
            if (scope === 'bestchange') {
                return '-'
            }
            else {
                return val.replace('Engine', '').replace('P2P', '');
            }
        }
    },
    template:   `
    <div class="card">
        <div class="card-header">
            <i class="fas fa-table me-1"></i>
            [[ title ]]
        </div>
        <div class="card-body">
            <loader v-if="!loaded"></loader>
            <table class="w-100 table table-striped table-hover" v-if="loaded">
                <thead class="bg-light">
                    <tr>
                        <th>Scope</th>
                        <th>Engine</th>
                        <th class="text-primary">Give</th>
                        <th class="text-primary">Symbol</th>
                        <th class="text-primary">Method</th>
                        <th class="text-success">Get</th>
                        <th class="text-success">Symbol</th>
                        <th class="text-success">Method</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="item in filtered_table">
                        <td><b>[[ item.scope ]]</b></td>
                        <td>[[ item.engine ]]</td>
                        <td class="text-primary"><b>[[ item.give.value ]]</b></td>
                        <td class="text-primary">[[ item.give.symbol ]]</td>
                        <td class="text-primary">[[ item.give.method ]]</td>
                        <td class="text-success"><b>[[ item.get.value ]]</b></td>
                        <td class="text-success">[[ item.get.symbol ]]</td>
                        <td class="text-success">[[ item.get.method ]]</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
    `
});


Vue.component('invoice-form', {
    delimiters: ['[[', ']]'],
    props: {
        header: {
            type: String,
            default: "Invoice Schema"
        },
        fld_placeholder: {
            type: String,
            default: 'Enter field name'
        },
    },
    data() {
        return {
            model: {
                icon: 'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0ic3ZnLWljb24iIHN0eWxlPSJ3aWR0aDogMWVtOyBoZWlnaHQ6IDFlbTt2ZXJ0aWNhbC1hbGlnbjogbWlkZGxlO2ZpbGw6IGN1cnJlbnRDb2xvcjtvdmVyZmxvdzogaGlkZGVuOyIgdmlld0JveD0iMCAwIDEwMjQgMTAyNCIgdmVyc2lvbj0iMS4xIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxwYXRoIGQ9Ik0xMTIuNDY2IDg5LjY1NmgzMTMuNjA2djE1My40MTZIMTEyLjQ2NnoiIGZpbGw9IiNGRkQ0NTIiIC8+PHBhdGggZD0iTTUwMS45NDggMzA2LjU5MmgxNzMuNjc4djE2LjA0NGgtMTczLjY3OHpNMTEyLjQ2NiAzOTIuOTAyaDIyNS40NzJ2MTYuMDQ0SDExMi40NjZ6TTExMi40NjYgNDQ2LjcxMmgyMjUuNDcydjE2LjA0NEgxMTIuNDY2ek0xMDQuNDQ0IDUzOS43M3YyNzkuODA0aDU3OC44MjhWNTM5LjczSDEwNC40NDR6IG01NjIuNzg0IDI2My43NkgxMjAuNDlWNTU1Ljc3NGg1NDYuNzM4djI0Ny43MTZ6IiBmaWxsPSIjNEE1NTVGIiAvPjxwYXRoIGQ9Ik0xMzkuMjA4IDU3NC40OTRoNTA5LjN2MjEwLjI3OEgxMzkuMjA4eiIgZmlsbD0iI0RGREZERiIgLz48cGF0aCBkPSJNNDc4LjMxNiA4OTMuNDIyaDIxNy45NzJ2MTYuMDQ0SDQ3OC4zMTZ6TTI1NS45NDYgNTQ3Ljc1MmgxNi4wNDR2MjYzLjc2aC0xNi4wNDR6TTU2My4yMjIgNTQ3Ljc1MmgxNi4wNDR2MjYzLjc2aC0xNi4wNDR6TTUwMi4yODQgNTQ3Ljc1MmgxNi4wNDR2MjYzLjc2aC0xNi4wNDR6TTE2NS4zMDYgMTE5LjQ1NmgxNi4wNDR2OTMuODE4aC0xNi4wNDR6TTI2Mi4xOTIgMTIyLjU5OHY1OC4wNDRsLTM2LjgyNC02Mi4xMzItMTQuOTIyIDQuMDg4djg3LjMxNmgxNi4wNDRWMTUxLjg3bDM2LjgyNiA2Mi4xMzIgMTQuOTIyLTQuMDg4VjEyMi41OTh6TTM1Ny42NjYgMTE5Ljg4NmwtMjMuODQyIDY2LjMxNi0yMy44NDgtNjYuMzE2LTE1LjA5NCA1LjQyNiAzMS4zOTQgODcuMzE0aDE1LjA5NGwzMS4zODgtODcuMzE0eiIgZmlsbD0iIzRBNTU1RiIgLz48cGF0aCBkPSJNNzkyLjAyIDI2OC41MjhsNC4xMTYtMi4yOTJWNDMuNTg4YzAtMTUuMTg4IDEyLjM1Mi0yNy41NDQgMjcuNTQtMjcuNTQ0VjBIMTA2LjEyMkM1My40MjQgMCAxMC41NSA0Mi44NzQgMTAuNTUgOTUuNTcydjg4NC44NDRjMCAyNC4wMyAxOS41MzQgNDMuNTg0IDQzLjUzOCA0My41ODRoNzY5LjU4OHYtMTYuMDQ0Yy0xNS4xODggMC0yNy41NC0xMi4zNTItMjcuNTQtMjcuNTRWNTEyLjI5bC00LjExNi0yLjI5MmMtNDMuNzc2LTI0LjQyNi03MC45NzItNzAuNjgtNzAuOTcyLTEyMC43MDggMC01MC4wNjIgMjcuMTk2LTk2LjMzNCA3MC45NzItMTIwLjc2MnogbS04Ny4wMTYgMTIwLjc2MmMwIDU0LjI1NCAyOC42NTIgMTA0LjUyOCA3NS4wODggMTMyLjMzOHY0NTguNzg4YTQzLjM3IDQzLjM3IDAgMCAwIDkuODMgMjcuNTRINTQuMDg2Yy0xNS4xNjIgMC0yNy40OTItMTIuMzUyLTI3LjQ5Mi0yNy41NFY5NS41NzJjMC00My44NSAzNS42NzYtNzkuNTI4IDc5LjUyNi03OS41MjhoNjgzLjhhNDMuMzggNDMuMzggMCAwIDAtOS44MyAyNy41NDR2MjEzLjMwOGMtNDYuNDM0IDI3LjgxMi03NS4wODYgNzguMTA2LTc1LjA4NiAxMzIuMzk0eiIgZmlsbD0iIzRBNTU1RiIgLz48cGF0aCBkPSJNNzgwLjA2NiA4NDMuMjR2MTM3LjE5NmMwIDI0LjAyIDE5LjU3IDQzLjU2NCA0My42MiA0My41NjQgMjQuMDIgMCA0My41NjItMTkuNTQ0IDQzLjU2Mi00My41NjRWODQzLjI0aC04Ny4xODJ6IG03MS4xNCAxMzcuMTk2YzAgMTUuMTcyLTEyLjM0NiAyNy41Mi0yNy41MTggMjcuNTItMTUuMjA0IDAtMjcuNTc2LTEyLjM0Ni0yNy41NzYtMjcuNTJ2LTEyMS4xNTJoNTUuMDk0djEyMS4xNTJ6TTgyMy42MzQgMGMtMjQuMDI0IDAtNDMuNTY4IDE5LjU0NC00My41NjggNDMuNTY2VjE4MC43Nmg4Ny4xODRWNDMuNTY2Qzg2Ny4yNSAxOS41NDQgODQ3LjY4NiAwIDgyMy42MzQgMHogbTI3LjU3MiAxNjQuNzE0aC01NS4wOTRWNDMuNTY2YzAtMTUuMTc0IDEyLjM0Ni0yNy41MjIgMjcuNTI0LTI3LjUyMiAxNS4yMDQgMCAyNy41NyAxMi4zNDYgMjcuNTcgMjcuNTIydjEyMS4xNDh6TTExMi40NjYgNTk2LjdoNTYyLjc4NHYxNi4wNDRIMTEyLjQ2NnoiIGZpbGw9IiM0QTU1NUYiIC8+PHBhdGggZD0iTTg1OS4yMjYgMjc3LjAxMmMtNjEuOSAwLTExMi4yNTggNTAuMzYtMTEyLjI1OCAxMTIuMjYgMCA2MS45MDIgNTAuMzU4IDExMi4yNiAxMTIuMjU4IDExMi4yNnMxMTIuMjYyLTUwLjM2IDExMi4yNjItMTEyLjI2YzAtNjEuOS01MC4zNjItMTEyLjI2LTExMi4yNjItMTEyLjI2eiIgZmlsbD0iI0ZGRDQ1MiIgLz48cGF0aCBkPSJNODU5LjIyOCAyMzUuMDVjLTg1LjAzNiAwLTE1NC4yMTggNjkuMTg2LTE1NC4yMTggMTU0LjIyNCAwIDg1LjAzNiA2OS4xOCAxNTQuMjE2IDE1NC4yMTggMTU0LjIxNiA4NS4wMzggMCAxNTQuMjI0LTY5LjE4IDE1NC4yMjQtMTU0LjIxNi0wLjAwMi04NS4wMzgtNjkuMTg4LTE1NC4yMjQtMTU0LjIyNC0xNTQuMjI0eiBtMCAyOTIuMzk2Yy03Ni4xOSAwLTEzOC4xNzQtNjEuOTg0LTEzOC4xNzQtMTM4LjE3MiAwLTc2LjE5IDYxLjk4NC0xMzguMTc4IDEzOC4xNzQtMTM4LjE3OHMxMzguMTc4IDYxLjk4OCAxMzguMTc4IDEzOC4xNzhjMCA3Ni4xODgtNjEuOTkgMTM4LjE3Mi0xMzguMTc4IDEzOC4xNzJ6IiBmaWxsPSIjNEE1NTVGIiAvPjxwYXRoIGQ9Ik03NTkuMTc0IDQxOC41NDJsLTE1LjM5NiA0LjUxMmExMjAuMDcyIDEyMC4wNzIgMCAwIDAgNiAxNi4wOTZsMTQuNTkyLTYuNjc0YTEwMy41NiAxMDMuNTYgMCAwIDEtNS4xOTYtMTMuOTM0eiBtMTIuNDYyLTg1LjczMmwtMTMuNDY0LTguNzIyYTEyMC43MiAxMjAuNzIgMCAwIDAtOC4yNzggMTUuMDUybDE0LjU3MiA2LjcwNmExMDQuNzc0IDEwNC43NzQgMCAwIDEgNy4xNy0xMy4wMzZ6IG0tMTIuMzk4IDI2Ljk2NmwtMTUuMzg2LTQuNTQ0YTExOS44MyAxMTkuODMgMCAwIDAtMy42NjYgMTYuNzhsMTUuODc2IDIuMjk4YTEwNC4wNDggMTA0LjA0OCAwIDAgMSAzLjE3Ni0xNC41MzR6IG0zMS45MS00OS4zODJsLTEwLjQ5OC0xMi4xMjZhMTIxLjI3IDEyMS4yNyAwIDAgMC0xMi4xNTQgMTIuMTEybDEyLjEwNiAxMC41M2ExMDYuNjE0IDEwNi42MTQgMCAwIDEgMTAuNTQ2LTEwLjUxNnogbS0zNi4xNTYgNzguNzU0bC0xNi4wNDQgMC4xMjZjMCA1LjY4MiAwLjQwMiAxMS40IDEuMTk2IDE2Ljk5bDE1Ljg4OC0yLjI1NmExMDUuMzY2IDEwNS4zNjYgMCAwIDEtMS4wNC0xNC44NnogbTE4My4yNDYtOTAuNTEyYTEyMC40ODIgMTIwLjQ4MiAwIDAgMC0xMy43MTYtMTAuMzQ2bC04LjcyMiAxMy40NjRhMTA0LjE1NiAxMDQuMTU2IDAgMCAxIDExLjg3NiA4Ljk2OGwxMC41NjItMTIuMDg2eiBtMjUuMjMgOTEuMDA4bDE2LjA0NC0wLjM2YTEyMC4zMiAxMjAuMzIgMCAwIDAtMS4xNi0xNi43MzhsLTE1Ljg4OCAyLjIyNGMwLjY3IDQuNzg0IDEuMDEgOS42NjIgMS4wMDQgMTQuODc0eiBtLTUzLjk5Mi0xMDkuNjYyYTExOS43MTYgMTE5LjcxNiAwIDAgMC0xNi4wODYtNi4wNThsLTQuNTU0IDE1LjM4NmM0LjczOCAxLjQgOS40MTYgMy4xNjYgMTMuOTE0IDUuMjQ0bDYuNzI2LTE0LjU3MnogbTQ5Ljg3NiA4MC4yNDJsMTUuNDA4LTQuNDhhMTE5Ljc4IDExOS43OCAwIDAgMC01Ljk3LTE2LjEwOGwtMTQuNjAyIDYuNjQ0YTEwNC41MzIgMTA0LjUzMiAwIDAgMSA1LjE2NCAxMy45NDR6IG0tMjAxLjMzNiA5My45ODRhMTIxLjExNCAxMjEuMTE0IDAgMCAwIDEwLjI4OCAxMy43MzZsMTIuMTI4LTEwLjUwOGExMDQuMTc2IDEwNC4xNzYgMCAwIDEtOC45Mi0xMS45MDhsLTEzLjQ5NiA4LjY4eiBtMTg5LjA1OC0xMjAuOTg2bDEzLjUwNi04LjY2YTEyMi4xODQgMTIyLjE4NCAwIDAgMC0xMC4yNTItMTMuNzU2bC0xMi4xNTggMTAuNDc2YTEwNi4wMiAxMDYuMDIgMCAwIDEgOC45MDQgMTEuOTR6IG0tNDQuOTUyIDE1MS4wNTRsNi42MjIgMTQuNjE0YTEyMC43MjQgMTIwLjcyNCAwIDAgMCAxNS4wODQtOC4xOWwtOC42MzgtMTMuNTE2YTEwNS4xMzQgMTA1LjEzNCAwIDAgMS0xMy4wNjggNy4wOTJ6IG0yNS4wMTItMTUuOTc4bDEwLjQ2NiAxMi4xNThhMTIxLjQ2IDEyMS40NiAwIDAgMCAxMi4xOC0xMi4wODRsLTEyLjA3Ni0xMC41NmExMDUuNDg0IDEwNS40ODQgMCAwIDEtMTAuNTcgMTAuNDg2eiBtLTUzLjUxOCAyNC4yMjRsMi4yMDQgMTUuODg4YTExOC41NSAxMTguNTUgMCAwIDAgMTYuODA4LTMuNTc4bC00LjQ2LTE1LjQwOGExMDQuNDIgMTA0LjQyIDAgMCAxLTE0LjU1MiAzLjA5OHogbTg1LjUzOC03My41MzZsMTUuMzc2IDQuNTg0YTExOS4wODQgMTE5LjA4NCAwIDAgMCAzLjcwOC0xNi43NzZsLTE1Ljg3OC0yLjMzYTEwMi40NDIgMTAyLjQ0MiAwIDAgMS0zLjIwNiAxNC41MjJ6IG0tMTIuNDY2IDI2LjkzOGwxMy40NTQgOC43NDRhMTIxLjMwOCAxMjEuMzA4IDAgMCAwIDguMzEtMTUuMDMybC0xNC41NjItNi43MzhhMTA0LjczNCAxMDQuNzM0IDAgMCAxLTcuMjAyIDEzLjAyNnogbS0xMDQuNTgyIDYyLjQxMmM1LjYzIDAuODEgMTEuMzkyIDEuMjE2IDE3LjEyIDEuMjE2di0xNi4wNDRjLTQuOTcyIDAtOS45NjQtMC4zNTYtMTQuODQyLTEuMDU0bC0yLjI3OCAxNS44ODJ6IG0zNC41MTQtMjM4LjA5NGMtNS42Mi0wLjgyLTExLjM4LTEuMjQ0LTE3LjEyNi0xLjI1NGwtMC4wMzIgMTYuMDQ0YzQuOTgyIDAuMDEgOS45NzYgMC4zNzYgMTQuODM4IDEuMDg2bDIuMzItMTUuODc2eiBtLTY3LjM5IDIyOC40MjZhMTIxLjY5OCAxMjEuNjk4IDAgMCAwIDE2LjA5NiA2LjAyMmw0LjUyMi0xNS4zOTZhMTA0LjQwNCAxMDQuNDA0IDAgMCAxLTEzLjk0NC01LjIxOGwtNi42NzQgMTQuNTkyeiBtMC4yNTYtMjE4LjkwNmExMTkuOTkyIDExOS45OTIgMCAwIDAtMTUuMDc4IDguMjI2bDguNjcgMTMuNDk2YTEwNC4wODggMTA0LjA4OCAwIDAgMSAxMy4wNTItNy4xMThsLTYuNjQ0LTE0LjYwNHogbS0yOS4wNSAyMDAuMzJhMTIyLjAxNCAxMjIuMDE0IDAgMCAwIDEzLjcyIDEwLjMxNmw4LjcxMi0xMy40NzZhMTA1LjIxOCAxMDUuMjE4IDAgMCAxLTExLjkwMi04Ljk0NmwtMTAuNTMgMTIuMTA2eiBtNjEuOTMyLTIwOS45MThhMTIwLjEyNCAxMjAuMTI0IDAgMCAwLTE2Ljc5MiAzLjYybDQuNDkyIDE1LjM5NmExMDQuOTQyIDEwNC45NDIgMCAwIDEgMTQuNTQ2LTMuMTI4bC0yLjI0Ni0xNS44ODh6TTkyMS44OCAzNDcuODA0bC04Ny44NDIgNzUuODA0LTM2LjY1NC00Mi4wNTQtMTIuMDk2IDEwLjU0IDQ3LjE0MiA1NC4wODYgOTkuOTI2LTg2LjIyOHoiIGZpbGw9IiM0QTU1NUYiIC8+PC9zdmc+',
                id: null,
                fields: [
                    {
                        name: 'AlipayID',
                        description: null
                    }
                ]
            },
            icons: {
                edit: 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KCjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+Cgo8IS0tIExpY2Vuc2U6IENDMCBMaWNlbnNlLiBNYWRlIGJ5IFNWRyBSZXBvOiBodHRwczovL3d3dy5zdmdyZXBvLmNvbS9zdmcvNDI3Nzk4L2VkaXQgLS0+CjxzdmcgZmlsbD0iIzAwMDAwMCIgdmVyc2lvbj0iMS4xIiBpZD0iTGF5ZXJfMSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWxuczp4bGluaz0iaHR0cDovL3d3dy53My5vcmcvMTk5OS94bGluayIgCgkgd2lkdGg9IjgwMHB4IiBoZWlnaHQ9IjgwMHB4IiB2aWV3Qm94PSIwIDAgMjAgMjAiIGVuYWJsZS1iYWNrZ3JvdW5kPSJuZXcgMCAwIDIwIDIwIiB4bWw6c3BhY2U9InByZXNlcnZlIj4KPHBhdGggZD0iTTE3LDIwSDFjLTAuNiwwLTEtMC40LTEtMVYzYzAtMC42LDAuNC0xLDEtMWg5djJIMnYxNGgxNHYtOGgydjlDMTgsMTkuNiwxNy42LDIwLDE3LDIweiIvPgo8cGF0aCBkPSJNOS4zLDEwLjdjLTAuNC0wLjQtMC40LTEsMC0xLjRsOS05YzAuNC0wLjQsMS0wLjQsMS40LDBzMC40LDEsMCwxLjRsLTksOUMxMC4zLDExLjEsOS43LDExLjEsOS4zLDEwLjd6Ii8+Cjwvc3ZnPg==',
                view: 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCEtLSBMaWNlbnNlOiBNSVQuIE1hZGUgYnkgZWxlbWVudC1wbHVzOiBodHRwczovL2dpdGh1Yi5jb20vZWxlbWVudC1wbHVzL2VsZW1lbnQtcGx1cy1pY29ucyAtLT4KPHN2ZyB3aWR0aD0iODAwcHgiIGhlaWdodD0iODAwcHgiIHZpZXdCb3g9IjAgMCAxMDI0IDEwMjQiIGNsYXNzPSJpY29uIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxwYXRoIGZpbGw9IiMwMDAwMDAiIGQ9Ik01MTIgMTYwYzMyMCAwIDUxMiAzNTIgNTEyIDM1MlM4MzIgODY0IDUxMiA4NjQgMCA1MTIgMCA1MTJzMTkyLTM1MiA1MTItMzUyem0wIDY0Yy0yMjUuMjggMC0zODQuMTI4IDIwOC4wNjQtNDM2LjggMjg4IDUyLjYwOCA3OS44NzIgMjExLjQ1NiAyODggNDM2LjggMjg4IDIyNS4yOCAwIDM4NC4xMjgtMjA4LjA2NCA0MzYuOC0yODgtNTIuNjA4LTc5Ljg3Mi0yMTEuNDU2LTI4OC00MzYuOC0yODh6bTAgNjRhMjI0IDIyNCAwIDExMCA0NDggMjI0IDIyNCAwIDAxMC00NDh6bTAgNjRhMTYwLjE5MiAxNjAuMTkyIDAgMDAtMTYwIDE2MGMwIDg4LjE5MiA3MS43NDQgMTYwIDE2MCAxNjBzMTYwLTcxLjgwOCAxNjAtMTYwLTcxLjc0NC0xNjAtMTYwLTE2MHoiLz48L3N2Zz4=',
                submit: 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KCjwhLS0gTGljZW5zZTogQ0MgQXR0cmlidXRpb24uIE1hZGUgYnkgSnVzdCBOaWNrOiBodHRwczovL2RyaWJiYmxlLmNvbS9MeXViYXJzaGNodWsgLS0+Cjxzdmcgd2lkdGg9IjgwMHB4IiBoZWlnaHQ9IjgwMHB4IiB2aWV3Qm94PSIwIDAgMTAyNCAxMDI0IiBjbGFzcz0iaWNvbiIgIHZlcnNpb249IjEuMSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNOTA1LjkyIDIzNy43NmEzMiAzMiAwIDAgMC01Mi40OCAzNi40OEE0MTYgNDE2IDAgMSAxIDk2IDUxMmE0MTguNTYgNDE4LjU2IDAgMCAxIDI5Ny4yOC0zOTguNzIgMzIgMzIgMCAxIDAtMTguMjQtNjEuNDRBNDgwIDQ4MCAwIDEgMCA5OTIgNTEyYTQ3Ny4xMiA0NzcuMTIgMCAwIDAtODYuMDgtMjc0LjI0eiIgZmlsbD0iZ3JlZW4iIC8+PHBhdGggZD0iTTYzMC43MiAxMTMuMjhBNDEzLjc2IDQxMy43NiAwIDAgMSA3NjggMTg1LjI4YTMyIDMyIDAgMCAwIDM5LjY4LTUwLjI0IDQ3Ni44IDQ3Ni44IDAgMCAwLTE2MC04My4yIDMyIDMyIDAgMCAwLTE4LjI0IDYxLjQ0ek00ODkuMjggODYuNzJhMzYuOCAzNi44IDAgMCAwIDEwLjU2IDYuNzIgMzAuMDggMzAuMDggMCAwIDAgMjQuMzIgMCAzNy4xMiAzNy4xMiAwIDAgMCAxMC41Ni02LjcyQTMyIDMyIDAgMCAwIDU0NCA2NGEzMy42IDMzLjYgMCAwIDAtOS4yOC0yMi43MkEzMiAzMiAwIDAgMCA1MDUuNiAzMmEyMC44IDIwLjggMCAwIDAtNS43NiAxLjkyIDIzLjY4IDIzLjY4IDAgMCAwLTUuNzYgMi44OGwtNC44IDMuODRhMzIgMzIgMCAwIDAtNi43MiAxMC41NkEzMiAzMiAwIDAgMCA0ODAgNjRhMzIgMzIgMCAwIDAgMi41NiAxMi4xNiAzNy4xMiAzNy4xMiAwIDAgMCA2LjcyIDEwLjU2ek0yMzAuMDggNDY3Ljg0YTM2LjQ4IDM2LjQ4IDAgMCAwIDAgNTEuODRMNDEzLjEyIDcwNGEzNi40OCAzNi40OCAwIDAgMCA1MS44NCAwbDMyOC45Ni0zMzAuNTZBMzYuNDggMzYuNDggMCAwIDAgNzQyLjA4IDMyMGwtMzAzLjM2IDMwMy4zNi0xNTYuOC0xNTUuNTJhMzYuOCAzNi44IDAgMCAwLTUxLjg0IDB6IiBmaWxsPSJncmVlbiIgLz48L3N2Zz4='
            },
            schema:{
                type: 'object',
                properties: {
                  firstName: {
                    type: 'string',
                  },
                  lastName: {
                    type: 'string',
                  },
                },
            },
            ui_schema: [
                {
                  component: 'input',
                  model: 'firstName',
                  fieldOptions: {
                    class: ['form-control', 'm-1'],
                    on: ['input'],
                    attrs: {
                      placeholder: this.fld_placeholder,
                      required: 'true',
                      title: this.fld_placeholder
                    },
                  },
                },
                {
                  component: 'button',
                  fieldOptions: {
                    class: ['badge', 'bg-primary'],
                    on: ['button'],
                    attrs: {
                      class: ['m-auto']
                    },
                    domProps: {
                        innerHTML: '+ comment',
                    }
                  },
                },
                {
                  component: 'input',
                  model: 'lastName',
                  fieldOptions: {
                    class: ['form-control', 'm-1'],
                    on: ['input'],
                    attrs: {
                      placeholder: this.fld_placeholder,
                      required: 'true',
                      title: this.fld_placeholder
                    },
                  },
                },
            ],
        }
    },
    methods: {
        on_description(prop){
            prop.description = '';
        },
        off_description(prop){
            prop.description = null;
        },
        add_field(){
            let prop = {
                name: '',
                description: null
            }
            this.model.fields.push(prop);
        },
        remove_field(name) {
            let new_fields = [];
            for (let i=0; i<this.model.fields.length; i++) {
                let fld = this.model.fields[i];
                if (name != fld.name) {
                    new_fields.push(fld);
                }
            }
            this.model.fields = new_fields;
        },
        change_logo(){
            let input = this.$refs.icon_file;
            input.click();
            console.log(input);
        }
    },
    mounted() {
        const icon_input = this.$refs.icon_file;
        let self = this;
        icon_input.addEventListener('change', (e) => {
            // Get a reference to the file
            const file = e.target.files[0];

            // Encode the file using the FileReader API
            const reader = new FileReader();
            reader.onloadend = () => {
                console.log(reader.result);
                self.model.icon = reader.result;
            };
            reader.readAsDataURL(file);
        });
    },
    template:   `
        <div class="card" style="width: 25rem;">
            <h5 class="card-header">
                <div class="w-100">
                    <img 
                        v-bind:src="model.icon" style="max-height: 3rem;max-width:3rem;cursor: pointer;" 
                        title="Edit Logo"
                        @click.prevent="change_logo"
                    />
                    <input class="form-control-sm" v-bind:placeholder="header" v-model="model.id">
                    <img v-bind:src="icons.edit" style="max-height: 2rem;max-width:2rem;cursor: pointer;float: right;"/>
                </div>
            </h5>
            <div class="card-body">
                <div class="form-group mb-1 p-3 border rounded-4 row" v-for="prop in model.fields">
                    <div class="col-4">
                        <span class="text-primary">[[ prop.name.replace(/\\s+/g, '') ]]</span>
                        <div class="alert alert-danger" v-if="!prop.name">Not Set</div>
                        <button 
                            class="badge btn btn-danger m-1"
                            @click="remove_field(prop.name)" 
                        >
                           remove
                        </button>
                    </div>
                    <div class="col">
                        <input class="form-control" type="text" v-model="prop.name" v-bind:placeholder="fld_placeholder"/>
                        <button 
                            class="badge btn btn-primary m-1" style="float: right;" 
                            v-if="prop.description === null"
                            @click="on_description(prop)"
                        >
                           + description
                        </button>
                        <textarea 
                            class="form-control alert alert-primary mt-1" v-model="prop.description" 
                            placeholder="Description"
                            v-if="prop.description !== null"
                        ></textarea>
                        <button 
                            class="badge btn btn-danger m-1" style="float: right;" 
                            v-if="prop.description !== null"
                            @click="off_description(prop)"
                        >
                            - description
                        </button>
                    </div>
                </div>
                <div class="w-100 text-center">
                    <button @click="add_field" class="btn btn-primary m-auto" title="add New field">+</button>
                    <img v-bind:src="icons.submit" style="max-height: 2rem;max-width:2rem;cursor: pointer;"/>
                </div>
            </div>
            <input ref="icon_file" type="file" style="display: none;">
        </div>
    `
});

Vue.component(
    'account-info',
    {
        delimiters: ['[[', ']]'],
        props: {
            account: {
                type: Object,
                default: null
            }
        },
        template: `
            <div class="w-100">
                <div v-if="!account" class="alert alert-warning text-center">
                    Empty
                </div>
                <div v-if="account">
                    <ul>
                        <li>
                            <span class="text-primary">ID:&ensp;</span> 
                            <span>[[ account.uid ]]</span>
                        </li>
                        <li>
                            <span class="text-primary">First name:&ensp;</span> 
                            <span>[[ account.first_name ]]</span>
                        </li>
                        <li>
                            <span class="text-primary">Last name:&ensp;</span> 
                            <span>[[ account.last_name ]]</span>
                        </li>
                        <li>
                            <span class="text-primary">Phone:&ensp;</span> 
                            <span>[[ account.phone ]]</span>
                        </li>
                        <li>
                            <span class="text-primary">Email:&ensp;</span> 
                            <span>[[ account.email ]]</span>
                        </li>
                        <li>
                            <span class="text-primary">Telegram:&ensp;</span> 
                            <span>[[ account.telegram ]]</span>
                        </li>
                        <li>
                            <span class="text-primary">Permissions:&ensp;</span> 
                            <span class="badge bg-primary text-light p-1 m-1" v-for="perm in account.permissions">[[ perm ]]</span>
                        </li>
                        <li>
                            <span class="text-primary">Is active:&ensp;</span> 
                            <span>[[ account.is_active ]]</span>
                        </li>
                        <li>
                            <span class="text-primary">Is verified:&ensp;</span> 
                            <span>[[ account.is_verified ]]</span>
                        </li>
                        <li>
                            <span class="text-primary">Is organization:&ensp;</span> 
                            <span>[[ account.is_organization ]]</span>
                        </li>
                        <li>
                            <span class="text-primary">Verified:&ensp;</span> 
                            <ul>
                                <li>
                                    <span class="text-primary">phone:&ensp;</span> 
                                    <span>[[ account.verified.phone ]]</span>
                                </li>
                                <li>
                                    <span class="text-primary">email:&ensp;</span> 
                                    <span>[[ account.verified.email ]]</span>
                                </li>
                                <li>
                                    <span class="text-primary">telegram:&ensp;</span> 
                                    <span>[[ account.verified.telegram ]]</span>
                                </li>
                            </ul>
                        </li>
                        
                    </ul>
                </div>
            </div>
        `
    }
);


Vue.component(
    'merchant-info',
    {
        delimiters: ['[[', ']]'],
        props: {
            merchant: {
                type: Object,
                default: null
            }
        },
        template: `
            <div class="w-100">
                <div v-if="!merchant" class="alert alert-warning text-center">
                    Empty
                </div>
                <div v-if="merchant">
                    <ul>
                        <li>
                            <span class="text-primary">Title:&ensp;</span> 
                            <span>[[ merchant.title ]]</span>
                        </li>
                        <li>
                            <span class="text-primary">URL:&ensp;</span> 
                            <span>[[ merchant.url ]]</span>
                        </li>
                        <li>
                            <span class="text-primary">Base currency:&ensp;</span> 
                            <span>[[ merchant.base_currency ]]</span>
                        </li>
                        <li>
                            <span class="text-primary">Identity:&ensp;</span> 
                            <ul>
                                <li>
                                    <span class="text-primary">DID:&ensp;</span> 
                                      <span>[[ merchant.identity.did.root ]]</span>
                                </li>
                            </ul>
                        </li>
                        <li>
                            <span class="text-primary">Paths:&ensp;</span> 
                            <ul>
                                <li>
                                    <span class="text-primary">admin:&ensp;</span> 
                                    <span>[[ merchant.paths.admin ]]</span>
                                </li>
                            </ul>
                        </li>
                        <li v-if="merchant.mass_payments.enabled">
                            <span class="text-primary">Mass payments:&ensp;</span> 
                            <ul>
                                <li>
                                    <span class="text-primary">Asset:&ensp;</span>
                                    <ul> 
                                        <li>
                                            <span class="text-primary">Method:&ensp;</span> 
                                            <span>[[ merchant.mass_payments.asset.code ]]</span>
                                        </li>
                                        <li>
                                            <span class="text-primary">Address:&ensp;</span> 
                                            <span>[[ merchant.mass_payments.asset.address ]]</span>
                                        </li>
                                    </ul>
                                </li>
                                <li>
                                    <span class="text-primary">Ratios:&ensp;</span>
                                    <ul> 
                                        <li>
                                            <span class="text-primary">Engine:&ensp;</span> 
                                            <span>[[ merchant.mass_payments.ratios.engine ]]</span>
                                        </li>
                                        <li>
                                            <span class="text-primary">Base currency:&ensp;</span> 
                                            <span>[[ merchant.mass_payments.ratios.base ]]</span>
                                        </li>
                                        <li>
                                            <span class="text-primary">Quote currency:&ensp;</span> 
                                            <span>[[ merchant.mass_payments.ratios.quote ]]</span>
                                        </li>
                                    </ul>
                                </li>
                                <li v-if="merchant.mass_payments.ledger">
                                    <span class="text-primary">Ledger:&ensp;</span>
                                    <ul> 
                                        <li>
                                            <span class="text-primary">ID:&ensp;</span> 
                                            <span>[[ merchant.mass_payments.ledger.id ]]</span>
                                        </li>
                                        <li>
                                            <span class="text-primary">Tags:&ensp;</span> 
                                            <span class="badge bg-primary" v-for="tag in merchant.mass_payments.ledger.tags">
                                                [[ tag ]]
                                            </span>
                                        </li>
                                        <li>
                                            <span class="text-primary">Participants:&ensp;</span>
                                            <ul>
                                                <li v-for="(members, role) in merchant.mass_payments.ledger.participants">
                                                    <span class="text-secondary">[[ role ]]:&ensp;</span>
                                                    <ul>
                                                        <li v-for="member in members">
                                                            [[ member ]]
                                                        </li>
                                                    </ul>
                                                </li>
                                            </ul>
                                        </li>
                                    </ul>
                                </li>
                            </ul>
                        </li>
                    </ul>
                </div>
            </div>
        `
    }
);

Vue.component(
    'kyc-info',
    {
        delimiters: ['[[', ']]'],
        props: {
            account_uid: {
                type: String,
                default: null
            },
            kyc_provider: {
                type: String,
                default: 'mts'
            }
        },
        data() {
            return {
                labels: {
                    exists_kyc_sessions: 'Есть активные KYC сессии',
                    clear_all: 'Очистить'
                },
                exists_kyc_sessions: false,
                clear_all_progress: false,
                kyc_empty: null,
                kyc: null
            }
        },
        methods: {
            refresh(){
                this.exists_kyc_sessions = false;
                let params = new URLSearchParams();
                params.append(`account_uid`, this.account_uid);
                params.append(`final`, 'no');
                let self = this;
                // проверяем сессии
                axios
                    .get(
                        '/api/kyc/' + this.kyc_provider,
                        {
                            params: params
                        }
                    )
                    .then(
                        (response) => {
                            self.exists_kyc_sessions = response.data.length > 0
                        }
                    ).catch(
                        (e) => {
                           //
                        }
                    ).finally(
                        (response) => {
                            //
                        }
                )
                // грузим KYC
                self.kyc_empty = null;
                axios
                    .get(
                        '/api/kyc/' + this.kyc_provider + '/' + this.account_uid + '/personal_data'
                    )
                    .then(
                        (response) => {
                            console.log(response.data);
                            self.kyc_empty = false;
                            self.kyc = response.data;
                        }
                    ).catch(
                        (e) => {
                           self.kyc_empty = true;
                        }
                    ).finally(
                        (response) => {
                            //
                        }
                )
            },
            clear_all(){
                if (this.clear_all_progress) {
                    return;
                }
                let self = this;
                self.clear_all_progress = true;
                axios
                    .delete(
                        '/api/kyc/mts/clear_all?account_uid=' + this.account_uid
                    )
                    .then(
                        (response) => {
                            self.refresh()
                        }
                    ).finally(
                        (response) => {
                            self.clear_all_progress = false
                        }
                    )
            }
        },
        mounted(){
            this.refresh();
        },
        watch: {
            account_uid: function(newVal, oldVal) { // watch it
              this.refresh();
            }
        },
        template: `
            <div class="w-100">
                <div v-if="exists_kyc_sessions" class="w-100">
                    <img src="/static/assets/img/pending-green2.gif" style="max-height: 15px;margin-left:4px;"/>
                    <span class="text-success">[[ labels.exists_kyc_sessions ]]</span>
                    <a :class="{'opacity-50': clear_all_progress}"  @click.prevent="clear_all" href="" class="text-lowercase text-danger" style="margin-left:2%;">x [[ labels.clear_all ]]</a>
                </div>
            
                <div v-if="kyc_empty === true" class="alert alert-primary text-center">
                    KYC Empty
                </div>
                <div v-if="kyc_empty === false" class="alert alert-primary">
                    <object-info 
                        :object="kyc"
                        :hidden="['verify', 'photos', 'metadata']"
                    >
                    </object-info>
                    <span>Details:</span>
                    <object-info 
                        :object="kyc.verify"
                    >
                    </object-info>
                </div>
                <loader-circle v-if="kyc_empty === null"></loader-circle>
            </div>
        `
    }
);


Vue.component(
    'object-info',
    {
        delimiters: ['[[', ']]'],
        props: {
            object: {
                type: Object
            },
            hidden: {
                type: Array,
                default(){
                    return [];
                }
            },
            header: {
                type: String
            },
            attr_class: {
                type: Object,
                default() {
                    return {}
                }
            }
        },
        computed: {
            shown(){
                let ret = {};
                for (const key in this.object) {
                    if (!this.hidden.includes(key)) {
                        ret[key] = this.object[key];
                    }
                }
                return ret;
            },
            is_empty(){
                return Object.keys(this.shown).length === 0;
            }
        },
        template: `
            <div class="w-100">
                <div>
                    <h6 class="text-secondary">[[ header ]]</h6>
                    <ul v-if="!is_empty">
                        <li v-for="(value, key) in shown">
                            <span class="text-primary">[[key]]:&ensp;</span> 
                            <span v-bind:class="attr_class[key] || attr_class[value]">[[ value ]]</span>
                        </li>
                    </ul>
                    <p v-if="is_empty" class="alert alert-warning w-100 text-center">[[ header ]] is empty</p>
                </div>
            </div>
        `
    }
);


Vue.component(
    'file-viewer',
    {
        delimiters: ['[[', ']]'],
        props: {
            url: String,
            name: {
                type: String,
                default(){return null}
            },
            mime_type: {
                type: String,
            },
            height: {
                type: Number,
                default(){return 300}
            }
        },
        data(){
            return {
                content_type: {
                    is_doc: true,
                    is_excel: false,
                    is_pdf: false,
                    is_image: false
                },
                component: null,
                j$: null,
                is_loading: false,
                error_msg: null,
            }
        },
        mounted(){
            this.refresh();
        },
        watch: {
            url: function(newVal, oldVal) {
               console.log('===');
               let self = this;
               setTimeout(function(){
                   self.refresh();
               },100); //delay is in milliseconds

            }
        },
        methods: {
            refresh(){
                $(this.$refs.document).css('height', this.height)
                for (let attr in this.content_type){
                    this.content_type[attr] = false;
                }
                if (this.component){
                    this.component.destroy();
                    this.component = null;
                }
                if (this.j$) {
                    this.j$.remove();
                }
                let self = this;
                this.error_msg = null;
                const options = {
                    onError: (e)=>{
                        console.log('Error', e)
                        self.error_msg = e.statusText;
                        self.is_loading = false;
                    },
                    onRendered: ()=>{
                        self.is_loading = false;
                    }
                }
                if (this.mime_type.endsWith('/pdf')) {
                    this.content_type.is_pdf = true;
                    this.component = jsPreviewPdf.init(
                        this.$refs.document, options
                    );
                }
                else if (this.mime_type.startsWith('image/')) {
                    this.content_type.is_image = true;
                    this.j$ = $('<img class="img-fluid img-thumbnail"></img>');
                    this.j$.attr('src', this.url).height(this.height).css('margin', 'auto');
                    this.j$.appendTo(this.$refs.document);
                }
                else if (this.mime_type.includes('document')) {
                    if (this.mime_type.includes('word')) {
                        this.content_type.is_doc = true;
                        this.component = jsPreviewDocx.init(
                            this.$refs.document, options
                        );
                    }
                    else if (this.mime_type.includes('sheet')) {
                        this.content_type.is_excel = true;
                        this.component = jsPreviewExcel.init(
                            this.$refs.document, options
                        );
                    }
                }
                if (this.component){
                    this.is_loading = true;
                    let p = this.component.preview(this.url);
                    if (p) {
                        p.then(() => {
                            self.is_loading = false;
                        }).catch(e => {
                            options.onError(e);
                        })
                    }
                }
            }
        },
        template: `
            <div class="w-100 text-center align-items-center bg-dark p-1">
                <div ref="document">
                    <div v-if="error_msg" class="alert alert-danger" style="margin: 0 20%;">
                        <h4>[[ error_msg ]]</h4>
                        <p>[[ url ]]</p>
                    </div>
                </div>
                <loader-circle v-if="is_loading" style="position: absolute;top:50%;left:0%"></loader-circle>
            </div>
        `
    }
);

Vue.component(
    'mass-payment-order-history',
    {
        delimiters: ['[[', ']]'],
        props: {
            api_base: {
                type: String
            },
            uid: {
                type: String
            }
        },
        data() {
            return {
                items: [],
                loading: false,
                error_msg: null,
                show_attachment_doc: null,
                window_height: 500,
                icons: {
                    download: 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCEtLSBMaWNlbnNlOiBQRC4gTWFkZSBieSBpY29uczg6IGh0dHBzOi8vaWNvbnM4LmNvbS9jL2ZsYXQtY29sb3ItaWNvbnMgLS0+Cjxzdmcgd2lkdGg9IjgwMHB4IiBoZWlnaHQ9IjgwMHB4IiB2aWV3Qm94PSIwIDAgNDggNDgiIHZlcnNpb249IjEiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgZW5hYmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgNDggNDgiPgogICAgPGcgZmlsbD0iIzE1NjVDMCI+CiAgICAgICAgPHBvbHlnb24gcG9pbnRzPSIyNCwzNy4xIDEzLDI0IDM1LDI0Ii8+CiAgICAgICAgPHJlY3QgeD0iMjAiIHk9IjQiIHdpZHRoPSI4IiBoZWlnaHQ9IjQiLz4KICAgICAgICA8cmVjdCB4PSIyMCIgeT0iMTAiIHdpZHRoPSI4IiBoZWlnaHQ9IjQiLz4KICAgICAgICA8cmVjdCB4PSIyMCIgeT0iMTYiIHdpZHRoPSI4IiBoZWlnaHQ9IjExIi8+CiAgICAgICAgPHJlY3QgeD0iNiIgeT0iNDAiIHdpZHRoPSIzNiIgaGVpZ2h0PSI0Ii8+CiAgICA8L2c+Cjwvc3ZnPg==',
                }
            }
        },
        watch: {
            uid: function(newVal, oldVal) {
              this.refresh();
            }
        },
        mounted () {
            this.refresh();
            this.window_height = window.innerHeight;
        },
        methods: {
            refresh() {
                let self = this;
                self.loading = true;
                console.log('Refresh history for ' + self.uid);
                axios
                    .get(self.api_base + '/' + self.uid + '/history')
                    .then(
                        (response) => {
                            let items = [];
                            for (let i=0; i<response.data.length; i++) {
                                let item = response.data[i];
                                item.utc = format_datetime_str(item.utc);
                                item.attachments = [];
                                if (item.payload){
                                    if (item.payload.attachments) {
                                        for (let j=0; j<item.payload.attachments.length; j++) {
                                            let desc = item.payload.attachments[j];
                                            item.attachments.push({
                                                id: desc.uid,
                                                name: desc.name,
                                                mime_type: desc.mime_type,
                                                url: self.api_base + '/' + desc.uid + '/file'
                                            });
                                        }
                                    }
                                }
                                items.push(item);
                            }
                            self.items = items;
                            //console.log(response.data);
                        }
                    ).catch(
                        (e) => {
                           self.error_msg = gently_extract_error_msg(e);
                        }
                    ).finally(
                        () => {
                            self.loading = false;
                        }
                )
            },
            attachment_clicked(a){
                this.show_attachment_doc = a;
            }
        },
        template: `
            <div class="w-100">
                <modal-window v-if="show_attachment_doc" @close="show_attachment_doc = null">
                    <div slot="header" class="w-100">
                        <h3>Document: <span class="text-primary">[[ show_attachment_doc.name || show_attachment_doc.id ]]</span>
                            <a v-bind:href="show_attachment_doc.url">
                                <img v-bind:src="icons.download" style="max-height: 1.5rem;max-width:1.5rem;cursor: pointer;" title="Download"/>
                            </a>
                            <button class="btn btn-danger" @click="show_attachment_doc = null" style="float: right;">
                                Close
                            </button>
                        </h3>
                    </div>
                    <div slot="body" class="w-100 text-center" v-bind:style="{'overflow': 'none', 'height': 3*window_height/4 + 'px'}">
                        <file-viewer
                            :url="show_attachment_doc.url"
                            :mime_type="show_attachment_doc.mime_type"
                            :height="3*window_height/4"
                        >
                        </file-viewer>
                    </div>
                    <div slot="footer" class="w-100 text-center">
                        
                    </div>
                </modal-window>
                <h6>UID: [[ uid ]]</h6>
                <div v-if="error_msg" class="alert alert-danger text-center">
                    <p>[[ error_msg ]]</p>
                </div>
                <div class="w-100 text-center" v-if="loading">
                    <loader></loader>
                </div>
                <div v-if="items">
                    <div class="w-100" v-for="item in items">
                        <div class="card w-100 mb-1" 
                            v-bind:class="{'border-success': item.status == 'success', 'border-danger': item.status == 'error', 'border-primary': item.status == 'processing'}" 
                        >
                          <div class="card-body">
                            <h5 class="card-title"
                                v-bind:class="{'text-success': item.status == 'success', 'text-danger': item.status == 'error', 'text-primary': item.status == 'processing'}"
                            >
                                <span class="text-secondary">Event:</span> [[ item.status ]]
                            </h5>
                            <h6 class="card-subtitle mb-2 text-muted">utc: [[ item.utc ]]</h6>
                            <p v-if="item.message" class="card-text badge bg-secondary"
                               
                            >
                                Message: [[ item.message ]]
                            </p>
                            <br v-if="item.attachments.length > 0"/>
                            <span v-if="item.attachments.length > 0" class="text-secondary">Attachments ([[ item.attachments.length ]]):</span>
                            <a @click.prevent="attachment_clicked(a)" v-bind:href="a.url" v-for="a in item.attachments" class="mr-n2">
                                [[a.name]] |
                            </a>
                          </div>
                        </div>
                    </div>
                </div>
            </div>
        `
    }
);

Vue.component(
    'filters-block',
    {
        delimiters: ['[[', ']]'],
        props: {
            items: {
                type: Array,
                default(){
                    return [
                        {
                            label: 'Filter1',
                            value: 'filter1',
                            checked: false,
                            class: 'btn-primary',
                            single: false,
                        },
                        {
                            label: 'Filter2',
                            value: 'filter2',
                            checked: false,
                            class: 'btn-danger',
                            single: false
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
            }
        },
        model: {
            prop: 'items',
            event: 'changed'
        },
        data() {
            return {
                labels: {
                    filters: 'Фильтры'
                }
            }
        },
        mounted() {
            this.refresh();
        },
        methods: {
            refresh() {

            },
            item_clicked(item){
                item.checked = !item.checked;
                if (item.checked) {
                    if (item.single) {
                        for (let i in this.items) {
                            let other = this.items[i];
                            if (other !== item) {
                                other.checked = false;
                            }
                        }
                    }
                    else {
                        for (let i in this.items) {
                            let other = this.items[i];
                            if (other !== item && other.single) {
                                other.checked = false;
                            }
                        }
                    }
                    this.$emit('changed')
                }
                else {
                    let others_check_count = 0;
                    for (let i in this.items) {
                        let other = this.items[i];
                        if (other.checked) {
                            others_check_count++;
                        }
                    }
                    if (others_check_count > 0) {
                        this.$emit('changed')
                    }
                    else {
                        item.checked = true
                    }
                }

            }
        },
        template: `
            <div>
                <span class="text-primary font-weight-bold">[[ labels.filters ]]:</span>
                <a @click.prevent="item_clicked(item)" v-for="item in items" class="btn m-1 btn-sm" v-bind:class="[item.class, item.checked ? '' : 'opacity-50']">
                    [[ item.label ]]
                </a>
            </div>
        `
    }
);


Vue.component(
    'data-table',
    {
        delimiters: ['[[', ']]'],
        emits: ['click_btn', 'click_link', 'click_cell', 'select_row'],
        props: {
            headers: {
                type: Array,
                default(){
                    return [
                        {
                            label: 'Column-1',
                            sortable: true,
                            hidden: false,
                        },
                        {
                            label: 'Column-2'
                        }
                    ]
                }
            },
            rows: {
                type: Array,
                default(){
                    return [
                        {
                            id: 'row-1',
                            cells: [
                                {
                                    id: 'cell[1,1]',
                                    text: 'Value[1,1]',
                                    class: 'bg bg-warning',
                                    buttons: [
                                        {
                                            id: 'btn1',
                                            label: 'Button1',
                                            class: 'm-1'
                                        },
                                        {
                                            id: 'btn2',
                                            label: 'Button2',
                                            class: 'm-1 btn btn-danger'
                                        }
                                    ]
                                },
                                {
                                    text: 'String[1,2]',
                                    class: 'text-success',
                                    icon: {
                                        src: '/static/assets/img/pending-green2.gif',
                                        style: 'max-height: 15px;margin-left:4px;'
                                    }
                                }
                            ]
                        },
                        {
                            id: 'row-2',
                            cells: [
                                {
                                    text: 'Value[2,1]',
                                    links: [
                                        {
                                            id: 'link-1',
                                            href: '/static/doc1.pdf',
                                            label: 'Link1'
                                        },
                                        {
                                            id: 'link-2',
                                            href: '/static/doc2.pdf',
                                            style: 'margin-left: 10px;'
                                        }
                                    ]
                                },
                                {
                                    id: 'xxx',
                                    text: null,
                                    badges: [
                                        {
                                            label: 'test-1',
                                            class: 'badge bg-primary'
                                        },
                                        {
                                            label: 'test-2',
                                            class: 'bg bg-success'
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            },
            searchable: {
                type: Boolean,
                default: false
            }
        },
        data() {
            return {
                rows_: null,
                table_api: null,
                loading: false,
                error_msg: null,
                selected_row: null
            }
        },
        mounted() {

            self = this;
            this.rows_ = this.rows;

            const renderRow = function(rowValue, tr, index){
                if (self.selected_row === index) {
                    tr.attributes.class = "table-primary";
                }
            }
            const renderCell = function(data, _cell, _dataIndex, _cellIndex) {
                _cell.childNodes = [];

                function extract_attributes(data_, node_ = null) {
                    let attrs = {}
                    if (node_){
                        attrs = node_.attributes || {};
                    }
                    attrs["row-index"] = data.row.index;
                    attrs["col-index"] = _cellIndex;
                    attrs["row-id"] = data.row.id;
                    if (data_) {
                        attrs["data-id"] = data_.id || "";
                        if (data_.class) {
                            if (attrs.class) {
                                attrs.class += ' ' + data_.class
                            } else {
                                attrs.class = data_.class;
                            }
                        }
                        if (data_.style) {
                            attrs.style = data_.style;
                        }
                    }
                    return attrs
                }

                let text_node = {
                    nodeName: "SPAN",
                    attributes: extract_attributes(data, _cell),
                    childNodes: [
                        {
                            nodeName: "#text",
                            data: data.text || ''
                        }
                    ]
                }
                _cell.childNodes.push(text_node);
                _cell.attributes = extract_attributes();

                if (data.icon) {
                    let attrs = extract_attributes(data.icon);
                    attrs.src = data.icon.src;
                    _cell.childNodes.push({
                        nodeName: "IMG",
                        attributes: attrs
                    })
                }
                if (data.buttons) {
                    for (let i=0; i<data.buttons.length; i++) {
                        let btn = data.buttons[i];
                        _cell.childNodes.push({
                            nodeName: "BUTTON",
                            attributes: extract_attributes(btn),
                            childNodes: [
                                {
                                    nodeName: "#text",
                                    data: btn.label || ''
                                }
                            ]
                        });
                    }
                }
                if (data.badges) {
                    for (let i=0; i<data.badges.length; i++) {
                        let badge = data.badges[i];
                        _cell.childNodes.push({
                            nodeName: "SPAN",
                            attributes: extract_attributes(badge),
                            childNodes: [
                                {
                                    nodeName: "#text",
                                    data: badge.label || ''
                                }
                            ]
                        });
                    }
                }
                if (data.links) {
                    for (let i=0; i<data.links.length; i++) {
                        let link = data.links[i];
                        let attrs = extract_attributes(link)
                        attrs.href = link.href,
                        _cell.childNodes.push({
                            nodeName: "A",
                            attributes: attrs,
                            childNodes: [
                                {
                                    nodeName: "#text",
                                    data: link.label || link.href
                                }
                            ]
                        });
                    }
                }
            }
            let columns = [];
            for (let i=0; i<this.headers.length; i++) {
                let hdr = this.headers[i];
                let col = {
                    select: i,
                    hidden: hdr.hidden || false,
                    sortable: hdr.sortable || false,
                    type: hdr.type || "string",
                    render: renderCell
                }
                columns.push(col);
            }
            this.table_api = new simpleDatatables.DataTable(
                this.$refs.table,
                {
                    rowRender: renderRow,
                    columns: columns,
                    paging: false,
                    searchable: this.searchable
                }
            );
            // console.log(columns)
            this.table_api.on("datatable.selectrow", (rowIndex, event) => {
                event.preventDefault();
                if (isNaN(rowIndex)) {
                    return;
                }
                let row_index_ = null;
                let row_id_ = null;
                try {
                    row_index_ = parseInt($(event.target).attr('row-index'));
                    row_id_ = $(event.target).attr('row-id')
                }catch (e){

                }
                self.$emit('select_row', row_index_, row_id_);
            });
            this.table_api.dom.addEventListener("click", event => {
                event.preventDefault();
                let id = null;
                let row_index = null;
                let col_index = null;
                let row_id = null;
                try {
                    row_index = parseInt($(event.target).attr('row-index'));
                    col_index = parseInt($(event.target).attr('col-index'));
                    id = $(event.target).attr('data-id')
                    row_id = $(event.target).attr('row-id')
                }catch (e){

                }
                if (event.target.matches("button")) {
                    self.$emit('click_btn', id, row_index, col_index, row_id);
                }
                else if (event.target.matches("a")) {
                    self.$emit('click_link', id, row_index, col_index, row_id);
                }
                else {
                    self.$emit('click_cell', id, row_index, col_index, row_id);
                    self.selected_row = row_index;
                    self.table_api.update()
                }
                //console.log(event.target);
            });
            this.refresh();

        },
        methods: {
            refresh(rows = null, unselect = true){
                let updData = [];

                function add(data, container){
                    const value = data.text || '';
                    container.push({
                        data: data,
                        order: value,
                        text: value
                    });
                }
                if (unselect) {
                    this.selected_row = null;
                }
                let table_rows = this.rows_;
                if (rows !== null) {
                    table_rows = rows;
                    this.rows_ = rows;
                }

                for (let i=0; i<table_rows.length; i++) {
                    let row = table_rows[i];
                    let dest = [];
                    let cells = row.cells;
                    for (let j=0; j<cells.length; j++) {
                        let d = cells[j];
                        d.row = {
                            id: row.id,
                            index: i
                        }
                        add(d, dest);
                    }
                    updData.push(dest);
                }
                this.table_api.data.data = updData;
                this.table_api.refresh();
            },

            clear(refresh = true){
                if (this.table_api) {
                    this.table_api.data.data = [];
                    if (refresh) {
                        this.table_api.update();
                    }
                }
            },

            set_loading(on){
                this.loading = on;
            },

            set_error(error_msg) {
                this.error_msg = error_msg;
            }
        },
        template: `
            <div>
                <loader-circle v-if="loading" style="position: absolute;top:50%;left:0%"></loader-circle>
                <div v-if="error_msg" class="alert alert-danger text-center">
                    <p>[[ error_msg ]]</p>
                </div>
                <table ref="table" class="w-100 table table-striped table-hover text-left" style="cursor:pointer;">
                    <thead>
                        <tr>
                            <th v-for="h in headers">[[ h.label ]]</th>
                        </tr>
                    </thead>
                    <tbody>
                    </tbody>
                </table>
            </div>
        `
    }
);

Vue.component(
    'mass-payment-order-status-editor',
    {
        delimiters: ['[[', ']]'],
        emits: ['on_edit', 'on_apply'],
        props: {
            statuses: {
                type: Array,
                default(){
                    return [
                        {
                            id: 'attachment',
                            label: 'Файлы/Справки',
                            class: 'text-secondary'
                        },
                        {
                            id: 'pending',
                            label: 'Вернуть в ожидание',
                            class: 'text-primary'
                        },
                        /*{
                            id: 'processing',
                            label: 'Взять в работу',
                            class: 'text-success'
                        },*/
                        {
                            id: 'success',
                            label: 'Выполнен',
                            class: 'text-success'
                        },
                        {
                            id: 'error',
                            label: 'Ошибка',
                            class: 'text-danger'
                        }
                    ]
                }
            },
            default_status: {
                type: String,
                default: 'attachment'
            },
            available_statuses: {
                type: Array,
                default: null
            }
        },
        data() {
            return {
                labels: {
                    edit_status: 'Редактировать статус',
                    decline_status: 'Отменить редактирование статуса',
                    attach_file: 'Приложить документ',
                    error_msg_apply: 'Приложите документ или оставьте комментарий'
                },
                editing: false,
                attachments: [],
                editable_statuses: [],
                upload_files_refs_initialized: false,
                error_msg: null,
                show_error: false,
                message: null,
                loading: false
            }
        },
        mounted(){
            this.init();
        },
        computed: {
            complex_error_msg(){
                return this.error_msg || this.labels.error_msg_apply
            }
        },
        methods: {
            enable_edit(on){
                if (on) {
                    this.init();
                }
                this.editing = on;
                this.$emit('on_edit', on)
            },
            init(){
                this.editable_statuses = [];
                this.show_error = false;
                this.message = null;
                this.error_msg = null;
                this.loading = false;
                this.attachments = [];
                for (let i=0; i<this.statuses.length; i++) {
                    let s = this.statuses[i];
                    if (this.available_statuses !== null) {
                        if (!this.available_statuses.includes(s.id)){
                            continue;
                        }
                    }
                    s.selected = s.id === this.default_status;
                    this.editable_statuses.push(s);
                }
            },
            init_upload_files_refs(){
                if (this.upload_files_refs_initialized) {
                    return;
                }
                let files = $(this.$refs.upload_file);
                const self = this;
                files.change(function(){
                    files.each(function (e) {
                        if (this.files && this.files[0]) {
                            let reader = new FileReader();
                            let name = this.files[0].name;
                            reader.onload = function (e) {
                                //console.log(e.target.result);
                                let d = {
                                    uid: generateUUID(),
                                    data: e.target.result,
                                    name: name
                                }
                                self.attachments.push(d);
                            }
                            reader.readAsDataURL(this.files[0]);
                        }
                    });
                });
                this.upload_files_refs_initialized = true;
            },
            append_attachment(uid, data, name, mime_type=null){
                this.init_upload_files_refs();
                let files = $(this.$refs.upload_file);
                files.trigger('click');
            },
            remove_attachment(item) {
                let new_values = [];
                for (let i=0; i<this.attachments.length; i++) {
                    let a = this.attachments[i];
                    if (a.uid !== item.uid) {
                        new_values.push(a);
                    }
                }
                this.attachments = new_values;
            },
            set_loading(on){
                this.loading = on
            },
            set_error(error_msg) {
                if (error_msg) {
                    this.error_msg = error_msg;
                    this.show_error = true
                }
                else {
                    this.error_msg = null;
                    this.show_error = false;
                }
            },
            on_checkbox_click(id) {
                for (let i=0; i<this.editable_statuses.length; i++) {
                    if (this.editable_statuses[i].id === id) {
                        this.editable_statuses[i].selected = true
                    }
                    else {
                        this.editable_statuses[i].selected = false
                    }
                }
            },
            apply(){
                this.show_error = false;
                this.error_msg = null;
                if (this.attachments.length < 1 && !this.message) {
                    this.show_error = true;
                    return
                }
                let selected_status = null;
                for (let i=0; i<this.editable_statuses.length; i++) {
                    if (this.editable_statuses[i].selected) {
                        selected_status = this.editable_statuses[i].id
                    }
                }
                this.$emit('on_apply', selected_status, this.attachments, this.message)
            }
        },
        template: `
            <div class="w-100 rounded p-1" v-bind:class="{'border-warning': editing, 'border': editing}">
                <div class="w-100 text-center">
                    <button @click="enable_edit(true)" class="btn btn-sm btn-danger" v-if="!editing">
                        <i class="fa-regular fa-pen-to-square"></i>
                        [[ labels.edit_status ]]
                    </button>
                    <button @click="enable_edit(false)" class="btn btn-sm btn-secondary" v-if="editing">
                        <i class="fa-regular fa-circle-xmark"></i>
                        [[ labels.decline_status ]]
                    </button>
                </div>
                <div class="w-100 row m-3" v-if="editing">
                    <div class="col" style="text-align: left;">
                        <div class="form-check" v-for="status in editable_statuses">
                          <input @click="on_checkbox_click(status.id)" v-bind:checked="status.selected" name="status_check" class="form-check-input" type="radio">
                          <label class="form-check-label" v-bind:class="status.class">
                            [[ status.id ]] <span>([[ status.label ]])</span>
                          </label>
                        </div>
                    </div>
                    <div class="col" style="text-align: left;">
                        <div v-for="a in attachments">
                            <a href="" class="text-danger"
                                @click.prevent="remove_attachment(a)"
                            >
                                <i class="fa-solid fa-xmark"></i>
                            </a>
                            <span class="text-primary">
                                [[ a.name ]]
                            </span>
                        </div>
                        <a href="" class="text-success"
                            @click.prevent="append_attachment(null, '', 'Name.pdf')"
                        >
                            <i class="fa-solid fa-plus"></i>
                            [[ labels.attach_file ]]
                        </a>
                        <input type="file" ref="upload_file" style="display: none;">
                    </div>
                </div>
                <div class="p-2" v-if="editing">
                    <div class="form-floating">
                      <textarea v-model="message" class="form-control" style="height: 100px"></textarea>
                      <label for="floatingTextarea2">Message</label>
                    </div>
                </div>
                <div class="w-100 text-center" v-if="editing">
                    <loader-circle v-if="loading"></loader-circle>
                    <div v-if="show_error" class="alert alert-danger text-center">
                        <p>[[ complex_error_msg ]]</p>
                    </div>
                    <button @click.prevent="apply" class="btn btn-sm btn-primary">
                        Apply
                    </button>
                </div>
            </div>
        `
    }
);

Vue.component(
    'files-navigator-modal',
    {
        delimiters: ['[[', ']]'],
        emits: ['close'],
        props: {
            header: {
                type: String,
                default: 'Files Navigator'
            }
        },
        data() {
            return {
                show: false,
                attachments: [],
                active: null,
                icons: {
                    download: 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCEtLSBMaWNlbnNlOiBQRC4gTWFkZSBieSBpY29uczg6IGh0dHBzOi8vaWNvbnM4LmNvbS9jL2ZsYXQtY29sb3ItaWNvbnMgLS0+Cjxzdmcgd2lkdGg9IjgwMHB4IiBoZWlnaHQ9IjgwMHB4IiB2aWV3Qm94PSIwIDAgNDggNDgiIHZlcnNpb249IjEiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgZW5hYmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgNDggNDgiPgogICAgPGcgZmlsbD0iIzE1NjVDMCI+CiAgICAgICAgPHBvbHlnb24gcG9pbnRzPSIyNCwzNy4xIDEzLDI0IDM1LDI0Ii8+CiAgICAgICAgPHJlY3QgeD0iMjAiIHk9IjQiIHdpZHRoPSI4IiBoZWlnaHQ9IjQiLz4KICAgICAgICA8cmVjdCB4PSIyMCIgeT0iMTAiIHdpZHRoPSI4IiBoZWlnaHQ9IjQiLz4KICAgICAgICA8cmVjdCB4PSIyMCIgeT0iMTYiIHdpZHRoPSI4IiBoZWlnaHQ9IjExIi8+CiAgICAgICAgPHJlY3QgeD0iNiIgeT0iNDAiIHdpZHRoPSIzNiIgaGVpZ2h0PSI0Ii8+CiAgICA8L2c+Cjwvc3ZnPg==',
                },
                window_height: 500
            }
        },
        mounted(){
            this.window_height = window.innerHeight;
        },
        methods: {
            open(attachments){
                this.attachments = attachments;
                if (attachments) {
                    this.active = attachments[0];
                }
                else {
                    this.active = null
                }
                this.show = true;
            },
            close(){
                this.show = false
            },
            select(a) {
                this.active = a;
            }
        },
        template: `
            <modal-window v-if="show" @close="$emit('close')" :width="'70%'">
                <div slot="header" class="w-100">
                    <h3 class="text-primary">
                        [[ header ]]
                        <button class="btn btn-danger" @click="close()" style="float: right;">
                            Close
                        </button>
                    </h3>
                </div>
                
                <div slot="body" class="w-100 text-center">
                    <div class="w-100">
                        <a 
                            @click.prevent="select(a)" 
                            v-for="a in attachments"
                            v-bind:class="{'bg-warning': a.uid === active.uid}" 
                            class="rounded p-2 link-offset-2 link-underline link-underline-opacity-50 m-2" 
                            href="#"
                        >
                            [[ a.name ]]
                        </a>
                    </div>
                    <div class="w-100 text-center mt-2">
                        <a v-bind:href="active.url" v-if="active" class="text-secondary" target="_blank">
                            <img v-bind:src="icons.download" style="max-height: 1.5rem; max-width: 1.5rem; cursor: pointer;" title="Download"/>
                            [[ active.name ]]
                        </a>    
                        <div class="border-top my-3"></div>
                        <file-viewer
                            v-if="active"
                            :url="active.url"
                            :mime_type="active.mime_type"
                            :height="2*window_height/3"
                        >
                        </file-viewer>
                    </div>
                </div>
                
                <div slot="footer" class="w-100 text-center">
                     
                </div>
            </modal-window>
        `
    }
);

Vue.component(
    'countdown-timer',
    {
        delimiters: ['[[', ']]'],
        emits: ['finished'],
        props: {
            seconds: {
                type: Number,
                default: 15
            }
        },
        data() {
            return {
                start: luxon.DateTime.local(),
                now: luxon.DateTime.local(),
                end: luxon.DateTime.local().plus({ seconds: this.seconds }),
                tick: null
            }
        },
        mounted(){
            this.tick = setInterval(() => {
              this.now = luxon.DateTime.local();
              if (this.finished){
                  this.restart();
                  this.$emit('finished')
              }
            }, 10)
        },
        methods: {
            restart(){
                this.start = luxon.DateTime.local();
                this.now = luxon.DateTime.local();
                this.end = luxon.DateTime.local().plus({ seconds: this.seconds });
                this.tick = null;
            }
        },
        computed: {
            total() {
              return this.end.diff(this.start).toObject()
            },
            remaining() {
              return this.end.diff(this.now).toObject()
            },
            elapsed() {
              return this.now.diff(this.start).toObject()
            },
            percent() {
              return this.elapsed.milliseconds / this.total.milliseconds * 100
            },
            display() {
               return luxon.Duration.fromObject(this.remaining).toFormat('hh:mm:ss')
            },
            finished() {
              return this.now >= this.end
            },
            gradient() {
              return {
                background: `radial-gradient(white 30%, transparent 61%),conic-gradient(#D53738 0% ${this.percent}%, transparent ${this.percent}% 100%)`
              }
            }
        },
        template: `
            <div style="align-items: center;display: flex;justify-content: center;padding: 3px;">
              <template>
                <time :style="gradient" style="border-radius: 50%;height: 20px;width: 20px;"></time>
              </template>
            </div>
        `
    }
);


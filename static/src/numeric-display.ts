export class NumericDisplay {
    public gas_name: string;
    private number_element: HTMLInputElement;
    private decimal_places: number = 2;
    private unit: string;                       

    constructor(
        number_id: string,
        gas_name: string,
        unit: string = "",                       
    ) {
        this.number_element = document.getElementById(number_id) as HTMLInputElement;
        this.gas_name = gas_name;
        this.unit = unit;                        
    }

    public updateValue(value: number) {
        const formattedConcentration = value.toFixed(this.decimal_places);
        
        this.number_element.textContent = `${formattedConcentration}${this.unit}`;
    }

    public changeGasType(gas: string, unit: string) {   
        this.gas_name = gas;
        this.unit = unit;                                
        this.number_element.textContent = `-.--${this.unit}`;
    }
}
